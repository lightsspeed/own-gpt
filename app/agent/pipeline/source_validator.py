from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.langsmith import traceable
from .source_policy import AnswerMode, SourcePolicy

logger = logging.getLogger(__name__)


@dataclass
class SourceValidationResult:
    valid: bool = True
    missing_refs: list[int] = field(default_factory=list)
    cited_count: int = 0
    required_count: int = 0
    unique_chunks_cited: int = 0
    total_citation_uses: int = 0
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


class SourceValidator:
    """
    Validates that the LLM's cited chunk references satisfy the AnswerMode's
    CitationContract requirements.

    Checks:
    1. If requires_evidence=True, at least min_evidence chunks must be cited.
    2. All cited chunk indices must exist in the ranked_chunks list.
    3. (Warning) If 3+ citation markers all point to the same chunk, flag low diversity.
    """

    @traceable(name="source_validator", metadata={"stage": "source_validator"})
    def validate(
        self,
        ref_indices: list[int],
        total_chunks: int,
        mode: AnswerMode,
    ) -> SourceValidationResult:
        contract = mode.contract

        if not contract.requires_evidence:
            return SourceValidationResult(
                valid=True,
                reason=f"mode={mode.policy.value} does not require evidence",
            )

        missing = [i for i in ref_indices if i >= total_chunks]

        if missing:
            return SourceValidationResult(
                valid=False,
                missing_refs=missing,
                cited_count=len(ref_indices),
                required_count=contract.min_evidence,
                reason=f"referenced chunks out of range: {missing} (max index={total_chunks - 1})",
            )

        if len(ref_indices) < contract.min_evidence:
            return SourceValidationResult(
                valid=False,
                cited_count=len(ref_indices),
                required_count=contract.min_evidence,
                reason=f"cited {len(ref_indices)} chunks but {contract.min_evidence} required",
            )

        # Diversity check: if 3+ citation markers all point to the same chunk
        unique_chunks = len(set(ref_indices))
        warnings: list[str] = []
        if len(ref_indices) >= 3 and unique_chunks == 1:
            warnings.append(
                f"all {len(ref_indices)} citations point to the same chunk "
                f"(Chunk {ref_indices[0]}). Consider citing different chunks for different claims."
            )

        logger.info(
            "stage=source_validator valid=true cited=%d required=%d unique=%d uses=%d warnings=%d",
            len(ref_indices),
            contract.min_evidence,
            unique_chunks,
            len(ref_indices),
            len(warnings),
        )

        return SourceValidationResult(
            valid=len(warnings) == 0,
            cited_count=len(ref_indices),
            required_count=contract.min_evidence,
            unique_chunks_cited=unique_chunks,
            total_citation_uses=len(ref_indices),
            reason="all citation requirements satisfied",
            warnings=warnings,
        )