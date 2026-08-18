"""
Stage 2f: Memory Learning (V3.8)

Purpose: Decide whether an interaction contains durable, explicitly-stated
user information worth persisting, and persist it through the existing
Memory V2 service so future decisions can use it.

V3.8 ORCHESTRATES Memory V2 — it never creates another memory system.
No new database, table, or vector store. All persistence goes through
app.services.memory.create_memory(), which enforces user isolation,
project isolation, authority/source metadata, deduplication, and
conflict handling.

Key architectural invariants:
  - AgentLearner NEVER executes tools, calls LLMs, or performs retrieval.
  - Only explicit user statements are candidates: store requests
    ("remember that ..."), declared preferences ("my favorite ... is ..."),
    declared facts ("my name is ..."), and corrections ("actually, ...").
  - Ambiguous input is SKIPPED, never guessed.
  - Greetings, ordinary questions, tool outputs, web results, and
    transient conversation details are never memorized.
  - Sensitive material (secrets, credentials, keys) is refused.
  - Learning runs only after validation: a failed answer is never learned.
  - Memory V2 failures are caught and reported in a structured
    LearningResult — the answer is never affected.

The learning gate, in order:
  Is this durable? -> Is it useful later? -> Was it explicitly stated?
  -> Is it safe to remember? -> Store through Memory V2.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.core.langsmith import traceable
from app.models.memory import (
    DOMAIN_EPISODIC,
    DOMAIN_PREFERENCE,
    DOMAIN_SEMANTIC,
    SOURCE_USER_DECLARED,
)

logger = logging.getLogger(__name__)


@dataclass
class LearningResult:
    """Structured outcome of one learning pass over an interaction."""
    memories_created: int = 0
    memories_updated: int = 0
    memories_skipped: int = 0
    reason: str = ""

    def __bool__(self) -> bool:
        return self.memories_created > 0 or self.memories_updated > 0


# ── Marker prefixes (lead-ins that signal explicit statements) ───────────────

# Explicit store requests: the remainder after the marker is the candidate.
_STORE_MARKERS = (
    re.compile(
        r"^(?:please\s+)?(?:remember|memorize|don'?t\s+forget)"
        r"\b(?:\s+(?:that|this|to))?[:\s]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:store|save)\s+(?:that|this(?:\s+fact)?|the fact that)\b[:\s]+",
        re.IGNORECASE,
    ),
)

# User corrections of a previous answer or memory.
_CORRECTION_MARKERS = (
    re.compile(
        r"^(?:actually|correction|wait|hold\s+on|scratch\s+that|"
        r"to\s+be\s+clear|to\s+clarify|i\s+meant|i\s+mean)[,!\s]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"^that'?s\s+(?:wrong|incorrect|not\s+(?:right|correct))[,!\s.]+(?:it'?s\s+)?",
        re.IGNORECASE,
    ),
    re.compile(r"^you'?re\s+wrong[,!\s.]+(?:it'?s\s+)?", re.IGNORECASE),
    re.compile(r"^(?:no|nope|nah)[,!\s]+(?:that'?s\s+not\s+right[,!\s]*)?", re.IGNORECASE),
)

# Conversational fillers removed from the front of the utterance.
_FILLER_MARKERS = (
    re.compile(r"^(?:well|ok|okay|so|hey|hi)[,\s]+", re.IGNORECASE),
    re.compile(r"^please\s+", re.IGNORECASE),
)

# ── Statement patterns: (pattern, domain). First match wins; the matched
#    span — cleaned — becomes the persisted statement. ─────────────────────────

_STATEMENT_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bmy\s+favorite\b[^!?.\n]{1,80}?\bis\b[^!?.\n]{1,80}", re.IGNORECASE), DOMAIN_PREFERENCE),
    (re.compile(r"\bi\s+(?:really\s+)?(?:prefer|love|enjoy)\b[^!?.\n]{1,120}", re.IGNORECASE), DOMAIN_PREFERENCE),
    (re.compile(r"\bi\s+like\b[^!?.\n]{1,120}", re.IGNORECASE), DOMAIN_PREFERENCE),
    (re.compile(r"\bi\s+use\b[^!?.\n]{1,120}", re.IGNORECASE), DOMAIN_PREFERENCE),
    (re.compile(r"\bmy\s+name\s+is\b[^!?.\n]{1,60}", re.IGNORECASE), DOMAIN_SEMANTIC),
    (re.compile(r"\bcall\s+me\b[^!?.\n]{1,60}", re.IGNORECASE), DOMAIN_SEMANTIC),
    (re.compile(r"\bi(?:'|\s)?am\b[^!?.\n]{1,120}", re.IGNORECASE), DOMAIN_SEMANTIC),
    (re.compile(r"\bi\s+work\b[^!?.\n]{1,120}", re.IGNORECASE), DOMAIN_SEMANTIC),
    (re.compile(r"\bi\s+(?:have|had)\s+been\b[^!?.\n]{1,120}", re.IGNORECASE), DOMAIN_SEMANTIC),
)

# Pronoun-only objects make a declared preference unresolvable -> skip.
_AMBIGUOUS_PREFERENCE_OBJECT = re.compile(
    r"^(?:it|this|that|you|them|these|those|"
    r"the\s+(?:answer|question|explanation|response|way|idea|plan|tool))$",
    re.IGNORECASE,
)
_AMBIGUOUS_PREFERENCE_PREFIX = ("the way ", "how you ", "your explanation ", "your answer ")

# Transient cues: mood/state or in-flight thinking — never durable when
# merely declared conversationally (explicit store requests still persist).
_TRANSIENCE_PATTERNS = re.compile(
    r"\b(?:wondering|thinking|asking|trying\s+to|looking\s+for|need(?:ing)?\s+help|"
    r"not\s+sure|unsure|curious\s+about|hungry|tired|busy|bored|happy|sad|angry|excited)\b",
    re.IGNORECASE,
)

# Temporal/event cues -> episodic domain for explicit store requests.
_EPISODIC_CUES = re.compile(
    r"\b(?:today|tonight|tomorrow|yesterday|last\s+night|last\s+week|next\s+week|"
    r"next\s+month|this\s+week|this\s+month|this\s+weekend|this\s+year|next\s+year|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"meeting|appointment|deadline|schedule|trip|vacation|holiday|event)\b",
    re.IGNORECASE,
)

# Sensitive material — never persisted, regardless of explicitness.
_SENSITIVE_PATTERNS = (
    re.compile(
        r"\b(?:api[_-]?key|passwords?|passphrase|secrets?|secret\s+key|credentials?"
        r"|auth(?:entication|orization)?|bearer)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:access\s+key|private\s+key|ssh\s+key|token|cvv|pin\s+code|ssn|social\s+security)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:credit\s+card|debit\s+card|bank\s+account|routing\s+number|license\s+key)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:sk-[a-z0-9_-]{8,}|AIza[a-z0-9_-]{8,}|ghp_[a-z0-9]{20,}|AKIA[a-z0-9]{16})\b",
        re.IGNORECASE,
    ),
)

# Explicitly non-durable acknowledgements / greetings.
_BARE_ACKS = frozenset({
    "hello", "hi", "hey", "thanks", "thank you", "thx", "yes", "no", "nope",
    "ok", "okay", "sure", "alright", "bye", "goodbye", "got it", "understood",
})

_QUESTION_STARTERS = re.compile(
    r"^(?:what|which|who|whose|whom|when|where|why|how|is|are|was|were|"
    r"do|does|did|can|could|would|should|will|shall)\b",
    re.IGNORECASE,
)

# Corrections referencing external pronouns cannot be resolved -> skip.
_UNRESOLVABLE_STARTERS = re.compile(r"^(?:it'?s|that'?s|this\s+is|he'?s|she'?s|they'?re)\b", re.IGNORECASE)


# ── Extraction helpers (pure, deterministic, no I/O) ─────────────────────────

def _strip_markers(text: str) -> tuple[str, str]:
    """Strip leading conversation markers.

    Returns (remainder, kind) where kind is one of "store", "correction",
    "plain". Markers repeat so stacked lead-ins ("ok, actually, ...") unwind.
    """
    t = (text or "").strip()
    kind = "plain"
    if not t:
        return t, "empty"
    changed = True
    while changed and t:
        changed = False
        for marker in _STORE_MARKERS:
            m = marker.match(t)
            if m:
                kind = "store"
                t = t[m.end():].strip()
                changed = True
                break
        if changed:
            continue
        for marker in _CORRECTION_MARKERS:
            m = marker.match(t)
            if m:
                kind = "correction"
                t = t[m.end():].strip()
                changed = True
                break
        if changed:
            continue
        for marker in _FILLER_MARKERS:
            m = marker.match(t)
            if m:
                t = t[m.end():].strip()
                changed = True
                break
    return t, kind


def _clean_statement(text: str) -> str:
    """Normalize a candidate statement: trim punctuation, drop a trailing
    "not X" clause from corrections, collapse whitespace."""
    s = text.strip().strip(" \t.,;:!?")
    s = re.sub(r",?\s+not\s+(?:a|an|the)?\s*[\w'’-]+$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \t.,;:!?")


def _is_ambiguous_preference(statement: str) -> bool:
    """True when a preference statement's object is a bare pronoun or an
    unresolvable reference ("I like it", "I like this")."""
    m = re.search(r"\b(?:like|love|enjoy|prefer|use)\b(.*)$", statement, re.IGNORECASE)
    obj = (m.group(1).strip().strip(".,;:!?") if m else statement).strip().lower()
    if _AMBIGUOUS_PREFERENCE_OBJECT.fullmatch(obj):
        return True
    return any(obj.startswith(p) for p in _AMBIGUOUS_PREFERENCE_PREFIX)


def _is_plain_declarative(text: str) -> bool:
    """True when the text is a self-contained declarative sentence
    (used only for the explicit store/correction fallback path)."""
    t = (text or "").strip()
    if not t or len(t) < 5 or len(t) > 200:
        return False
    if len(re.findall(r"[A-Za-z]+", t)) < 2:
        return False
    if t.endswith(("?", "!")):
        return False
    lowered = t.lower()
    if _QUESTION_STARTERS.match(lowered):
        return False
    if _UNRESOLVABLE_STARTERS.match(lowered):
        return False
    if lowered.strip(" .,!?;:") in _BARE_ACKS:
        return False
    return True


def _classify(remainder: str, kind: str) -> Optional[tuple[str, str]]:
    """Map the remainder to (statement, domain) or None.

    Patterns describe durable, explicitly-stated content. When no pattern
    matches BUT the user gave an explicit store request or correction, a
    plain declarative remainder is still persisted. Everything else is
    skipped rather than guessed.
    """
    text = remainder.strip()
    if not text or text.endswith("?"):
        return None

    for pattern, domain in _STATEMENT_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        statement = _clean_statement(m.group(0))
        if len(statement) < 5 or len(statement) > 200:
            continue
        if domain == DOMAIN_PREFERENCE and _is_ambiguous_preference(statement):
            continue
        if kind == "plain" and _TRANSIENCE_PATTERNS.search(statement):
            continue
        return statement, domain

    if kind in ("store", "correction") and _is_plain_declarative(text):
        domain = DOMAIN_EPISODIC if _EPISODIC_CUES.search(text) else DOMAIN_SEMANTIC
        statement = _clean_statement(text)
        if len(statement) >= 5:
            return statement, domain
    return None


def _contains_sensitive(statement: str) -> bool:
    return any(p.search(statement) for p in _SENSITIVE_PATTERNS)


# ── Learner ───────────────────────────────────────────────────────────────────

class AgentLearner:
    """
    V3.8 learning stage. Pure orchestrator over Memory V2:
      - extracts explicit, durable user statements from the question
      - persists them through app.services.memory.create_memory()
      - never executes tools, never calls the LLM, never retrieves

    Session and embedding provider are resolved lazily so hermetic tests
    can inject sqlite sessions and fake embedders without touching the
    real infrastructure.
    """

    def __init__(self, session_factory=None, embed=None) -> None:
        self._session_factory = session_factory
        self._embed = embed

    def _resolve_embed(self):
        if self._embed is not None:
            return self._embed
        try:
            from app.services.embeddings import build_embedding_provider
            provider = build_embedding_provider()
            return provider.embed if provider is not None else None
        except Exception as exc:
            logger.warning(
                "agent_learning_embed_provider_failed error_type=%s error=%s",
                type(exc).__name__, exc,
            )
            return None

    @traceable(name="agent_learn", metadata={"stage": "2f"})
    def learn(
        self,
        question: str,
        answer: str | None = None,
        intent: object | None = None,
        execution: object | None = None,
        validation: object | None = None,
        context: object | None = None,
    ) -> LearningResult:
        """
        Learn from one interaction. Returns a structured LearningResult;
        never raises (Memory V2 failures are absorbed so the answer is
        never affected).

        Gates:
          1. Validation — learn only from validated answers.
          2. Execution   — never learn when execution failed or was blocked.
          3. Identity    — memories are always user-scoped.
          4. Extraction  — explicit, durable statements only.
          5. Safety      — sensitive material is refused.
        """
        # ── Gate 1: validation ───────────────────────────────────────────────
        if validation is None or not getattr(validation, "valid", False):
            logger.info("agent_learning_gate_closed gate=validation")
            return LearningResult(
                memories_skipped=1,
                reason="validation failed — not learning from this interaction",
            )

        # ── Gate 2: execution integrity ──────────────────────────────────────
        status = getattr(execution, "status", None) or ""
        if status in ("failed", "blocked"):
            logger.info("agent_learning_gate_closed gate=execution status=%s", status)
            return LearningResult(
                memories_skipped=1,
                reason=f"execution {status} — not learning from this interaction",
            )

        # ── Gate 3: identity (user isolation) ────────────────────────────────
        user_id = getattr(context, "user_id", None) or ""
        if not user_id:
            return LearningResult(
                memories_skipped=1,
                reason="no user identity — cannot persist a scoped memory",
            )

        # ── Gate 4: extraction (durable + explicit) ──────────────────────────
        remainder, kind = _strip_markers(question or "")
        candidate = _classify(remainder, kind) if remainder else None
        if candidate is None:
            logger.info(
                "agent_learning_no_candidate intent=%s question=%r",
                getattr(intent, "intent", None), (question or "")[:80],
            )
            return LearningResult(
                memories_skipped=1,
                reason="no durable, explicitly-stated information found",
            )
        statement, domain = candidate

        # ── Gate 5: safety ───────────────────────────────────────────────────
        if _contains_sensitive(statement):
            logger.info("agent_learning_refused_sensitive statement=%r", statement[:80])
            return LearningResult(
                memories_skipped=1,
                reason="candidate contains sensitive material — refused to store",
            )

        # ── Persist through Memory V2 (never directly) ───────────────────────
        try:
            from app.core.database import SyncSessionLocal
            from app.services.memory import create_memory, find_memory_by_statement

            session_factory = self._session_factory or SyncSessionLocal
            project_id = getattr(context, "project_id", None) or None
            session_id = getattr(context, "session_id", None) or None
            embed = self._resolve_embed()

            with session_factory() as db:
                if find_memory_by_statement(
                    db, user_id, statement, project_id=project_id
                ) is not None:
                    return LearningResult(
                        memories_skipped=1,
                        reason="duplicate memory already exists",
                    )
                entity = create_memory(
                    db,
                    user_id=user_id,
                    statement=statement,
                    domain=domain,
                    source=SOURCE_USER_DECLARED,
                    project_id=project_id,
                    source_conversation_id=session_id,
                    embed=embed,
                )
                updated = 1 if entity.supersedes_id else 0
                logger.info(
                    "agent_learning_stored user_id=%s project_id=%s domain=%s "
                    "supersedes=%s statement=%r",
                    user_id, project_id, domain, bool(entity.supersedes_id), statement[:80],
                )
                return LearningResult(
                    memories_created=1,
                    memories_updated=updated,
                    reason="stored via Memory V2",
                )
        except Exception as exc:
            logger.warning(
                "agent_learning_persist_failed user_id=%s error_type=%s error=%s",
                user_id, type(exc).__name__, exc,
            )
            return LearningResult(
                memories_skipped=1,
                reason=f"memory service failure — answer unaffected: {exc}",
            )