"""Phase 3.3 — small, deterministic Markdown integrity layer.

The OwnGPT streaming layer previously dropped whitespace/newline boundaries
between provider deltas; that root cause is fixed in the SSE assembly path
(app/api/endpoints/chat.py `_flatten_content`). This module is the small,
conservative safety net for residual structural Markdown defects.

Scope (repairs ONLY obvious structural defects):
- heading markers glued to prose or missing the required trailing space
- horizontal rules glued to prose or to a following heading
- fenced-code openers glued to prose

Never (by design):
- modifies fenced code content (code is opaque data)
- modifies URLs, inline code contents, or citation markers
- rewrites words, performs spell correction, or reconstructs lost spaces
- changes semantic content

The function is line-based, fence-aware, deterministic, and idempotent:

    normalize_markdown(normalize_markdown(text)) == normalize_markdown(text)
"""

from __future__ import annotations

import re

# Heading marker without the required trailing space: "###Title".
_HEADING_SPACE_RE = re.compile(r"^(#{1,6})(?=[^#\s])")

# Heading marker glued to prose on the same line: "text### Heading".
_HEADING_GLUE_RE = re.compile(r"(?<![#\s`])(#{2,6})(?=\s)")

# Fenced-code opener glued to prose: "Here is the configuration:```yaml".
_FENCE_GLUE_RE = re.compile(r"(?<=[^\s\n])(```+)")

# Horizontal rule glued to prose (end of line) or to a heading:
# "necessary.---" or "necessary.---### Core Concepts".
_HR_GLUE_RE = re.compile(r"(?<=[^\s\n])(---)(?=\s*$|#{1,6})")

# A fenced-code opener/closer at (up to 3 spaces of) line start.
_FENCE_MARK_RE = re.compile(r"^\s{0,3}(```+)")

# Context that must never be treated as glued prose (URLs / citation targets).
_URLISH_RE = re.compile(r"https?://|www\.|\]\(|\w[-\w]*\.\w{2,}/")

# Structural marker pieces need blank-line separation from surrounding text.
_MARKER_PIECE_RE = re.compile(r"\s*(?:#{1,6}\s|---|```+)")


def _first_glue(line: str) -> tuple[str, re.Match] | None:
    """Return the leftmost structural marker glued to prose inside a line."""
    best = None
    for name, rgx in (
        ("heading", _HEADING_GLUE_RE),
        ("fence", _FENCE_GLUE_RE),
        ("hr", _HR_GLUE_RE),
    ):
        m = rgx.search(line)
        if m and (best is None or m.start() < best[1].start()):
            best = (name, m)
    return best


def _expand_glues(line: str) -> list[str]:
    """Split glued structural markers from prose inside a single line.

    Returns the pieces of the original line: plain prose stays untouched
    (glued fragments are re-joined with no separator), while heading, rule,
    and fence markers become standalone pieces.
    """
    pieces: list[str] = []
    rest = line
    while True:
        found = _first_glue(rest)
        if found is None or found[1].start() == 0:
            pieces.append(rest)
            break
        name, m = found
        if name == "heading":
            guard = rest[max(0, m.start() - 240):m.start()]
            if _URLISH_RE.search(guard):
                # Likely inside/near a URL or link target — never split;
                # keep the segment verbatim and continue past the marker.
                pieces.append(rest[:m.end()])
                rest = rest[m.end():]
                continue
        pieces.append(rest[:m.start()])
        rest = rest[m.start():]
    return pieces


def _assemble(pieces: list[str]) -> list[str]:
    """Re-join prose fragments and separate marker pieces with blank lines."""
    out: list[str] = []
    prev_marker = False
    for piece in pieces:
        marker = bool(_MARKER_PIECE_RE.match(piece))
        if not marker and not prev_marker and out:
            out[-1] += piece
            continue
        if out and (marker or prev_marker):
            out.append("")
        out.append(piece)
        prev_marker = marker
    return out


def normalize_markdown(text: str) -> str:
    """Apply conservative structural Markdown normalization.

    Line-based and fence-aware: content inside fenced code blocks is passed
    through verbatim. Deterministic and idempotent.
    """
    if not isinstance(text, str) or not text:
        return text
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    in_fence = False
    for line in normalized.split("\n"):
        if in_fence:
            # Code is opaque data — never normalize inside fenced blocks.
            out.append(line)
            if _FENCE_MARK_RE.match(line):
                in_fence = False
            continue
        if _FENCE_MARK_RE.match(line):
            out.append(line)
            in_fence = True
            continue
        assembled = _assemble(_expand_glues(line))
        for piece in assembled:
            out.append(_HEADING_SPACE_RE.sub(lambda m: m.group(1) + " ", piece))
        if any(_FENCE_MARK_RE.match(p) for p in assembled):
            in_fence = True
    return "\n".join(out)