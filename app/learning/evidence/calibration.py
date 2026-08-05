"""
Confidence Calibration — measures how well predicted confidence matches actual outcomes.

Produces:
  - Reliability curve (confidence buckets vs actual acceptance rate)
  - Expected Calibration Error (ECE)
  - Per-bucket gap analysis
  - Overconfidence / underconfidence detection
  - Calibration Findings
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from ..storage.sqlite import LearningStore
from .models import (
    Evidence, EvidenceStrength, RootCause, RootCauseCategory,
    Finding, FindingCategory,
)

logger = logging.getLogger(__name__)

NUM_BUCKETS = 10  # 0-10%, 10-20%, ..., 90-100%


@dataclass
class CalibrationBucket:
    bucket: str = ""             # e.g. "80-90%"
    bucket_idx: int = 0          # 0-9
    lower: float = 0.0
    upper: float = 0.0
    count: int = 0
    avg_confidence: float = 0.0
    accept_rate: float = 0.0     # actual outcome (accepted=True)
    thumb_up_rate: float = 0.0
    gap: float = 0.0             # confidence - accept_rate (positive = overconfidence)

    def to_dict(self) -> dict:
        return {
            "bucket": self.bucket,
            "count": self.count,
            "avg_confidence": round(self.avg_confidence, 3),
            "accept_rate": round(self.accept_rate, 3),
            "thumb_up_rate": round(self.thumb_up_rate, 3),
            "gap": round(self.gap, 3),
        }


@dataclass
class CalibrationReport:
    buckets: list[CalibrationBucket] = field(default_factory=list)
    ece: float = 0.0                           # Expected Calibration Error
    max_overconfidence_bucket: Optional[str] = None
    max_underconfidence_bucket: Optional[str] = None
    total_records_analyzed: int = 0
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "buckets": [b.to_dict() for b in self.buckets],
            "ece": round(self.ece, 4),
            "max_overconfidence_bucket": self.max_overconfidence_bucket,
            "max_underconfidence_bucket": self.max_underconfidence_bucket,
            "total_records_analyzed": self.total_records_analyzed,
            "findings": [f.to_dict() for f in self.findings],
        }


class ConfidenceCalibration:
    """Analyze confidence calibration using the Learning Ledger."""

    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self) -> CalibrationReport:
        rows = self._store.query_sql("""
            SELECT record_id, confidence, accepted, thumb
            FROM learning_records
            WHERE confidence > 0 AND confidence IS NOT NULL
        """)
        if not rows:
            return CalibrationReport()

        buckets = [CalibrationBucket(
            bucket_idx=i,
            lower=i / NUM_BUCKETS,
            upper=(i + 1) / NUM_BUCKETS,
            bucket=f"{int(i * 10)}-{int((i + 1) * 10)}%",
        ) for i in range(NUM_BUCKETS)]
        record_ids_by_bucket: dict[str, list[str]] = {b.bucket: [] for b in buckets}

        for r in rows:
            conf = r["confidence"]
            idx = min(int(conf * NUM_BUCKETS), NUM_BUCKETS - 1)
            b = buckets[idx]
            b.count += 1
            b.avg_confidence += conf
            if r.get("accepted"):
                b.accept_rate += 1.0
            if r.get("thumb") == "up":
                b.thumb_up_rate += 1.0
            if r.get("record_id"):
                record_ids_by_bucket[b.bucket].append(r["record_id"])

        total = sum(b.count for b in buckets)
        ece_sum = 0.0
        for b in buckets:
            if b.count > 0:
                b.avg_confidence /= b.count
                b.accept_rate /= b.count
                b.thumb_up_rate /= b.count
                b.gap = round(b.avg_confidence - b.accept_rate, 3)
                ece_sum += (b.count / total) * abs(b.gap)

        ece = ece_sum
        overconf_bucket = max(buckets, key=lambda b: b.gap if b.count >= 10 else -999)
        underconf_bucket = min(buckets, key=lambda b: b.gap if b.count >= 10 else 999)
        findings = self._generate_findings(buckets, ece, record_ids_by_bucket)

        return CalibrationReport(
            buckets=buckets,
            ece=ece,
            max_overconfidence_bucket=overconf_bucket.bucket if overconf_bucket.count >= 10 else None,
            max_underconfidence_bucket=underconf_bucket.bucket if underconf_bucket.count >= 10 else None,
            total_records_analyzed=total,
            findings=findings,
        )

    def _generate_findings(
        self,
        buckets: list[CalibrationBucket],
        ece: float,
        record_ids_by_bucket: Optional[dict[str, list[str]]] = None,
    ) -> list[Finding]:
        record_ids_by_bucket = record_ids_by_bucket or {}
        findings = []

        # Check for severe overconfidence (high confidence but low acceptance)
        for b in buckets:
            if b.count >= 20 and b.avg_confidence >= 0.70 and b.gap > 0.25:
                obs = [
                    f"Bucket {b.bucket}: confidence={b.avg_confidence:.1%}, actual accept={b.accept_rate:.1%}",
                    f"Overconfidence gap: {b.gap:.1%}",
                    f"Sample: {b.count} records",
                ]
                evidence = Evidence(
                    category="calibration_drift",
                    strength=EvidenceStrength(
                        sample_size=b.count,
                        agreement=1.0 - abs(b.gap),
                        trend="stable",
                        consistency="stable" if b.count >= 50 else "insufficient",
                        confidence=0.85,
                    ),
                    observations=obs,
                    supporting_record_ids=record_ids_by_bucket.get(b.bucket, []),
                )
                findings.append(Finding(
                    category=FindingCategory.CALIBRATION_DRIFT,
                    severity="high" if b.gap > 0.35 else "medium",
                    title=f"Overconfidence in {b.bucket} bucket ({b.gap:.0%} gap)",
                    description=f"Model predicts {b.avg_confidence:.0%} confidence but only {b.accept_rate:.0%} of answers are accepted.",
                    root_cause=RootCause(
                        category=RootCauseCategory.OVERCONFIDENCE,
                        explanation=f"The evaluation pipeline overestimates confidence in the {b.bucket} range. "
                                    f"Predicted {b.avg_confidence:.0%}, actual {b.accept_rate:.0%}. "
                                    f"This suggests the confidence heuristic does not reflect real user satisfaction.",
                        confidence=min(0.5 + b.gap, 0.95),
                        evidence=evidence,
                    ),
                    evidence=evidence,
                    recommendation_text=f"Review confidence scoring for queries in the {b.bucket} range. "
                                        f"Consider calibrating the evaluation thresholds or adding a confidence correction factor.",
                    signature=f"calibration|overconfidence|{b.bucket}",
                ))

        # Check for underconfidence (low confidence but high acceptance)
        for b in buckets:
            if b.count >= 20 and b.avg_confidence <= 0.40 and b.gap < -0.20:
                obs = [
                    f"Bucket {b.bucket}: confidence={b.avg_confidence:.1%}, actual accept={b.accept_rate:.1%}",
                    f"Underconfidence gap: {b.gap:.1%}",
                    f"Sample: {b.count} records",
                ]
                evidence = Evidence(
                    category="calibration_drift",
                    strength=EvidenceStrength(
                        sample_size=b.count,
                        agreement=1.0 - abs(b.gap),
                        trend="stable",
                        consistency="stable" if b.count >= 50 else "insufficient",
                        confidence=0.80,
                    ),
                    observations=obs,
                    supporting_record_ids=record_ids_by_bucket.get(b.bucket, []),
                )
                findings.append(Finding(
                    category=FindingCategory.CALIBRATION_DRIFT,
                    severity="medium",
                    title=f"Underconfidence in {b.bucket} bucket ({-b.gap:.0%} gap)",
                    description=f"Model predicts {b.avg_confidence:.0%} confidence but {b.accept_rate:.0%} of answers are accepted — answers are better than expected.",
                    root_cause=RootCause(
                        category=RootCauseCategory.LOW_CONFIDENCE,
                        explanation=f"The evaluation pipeline underestimates quality in the {b.bucket} range. "
                                    f"Predicted {b.avg_confidence:.0%}, actual {b.accept_rate:.0%}.",
                        confidence=min(0.5 - b.gap, 0.90),
                        evidence=evidence,
                    ),
                    evidence=evidence,
                    recommendation_text=f"Review confidence scoring for low-confidence queries. "
                                        f"Answers in the {b.bucket} range perform better than predicted — thresholds may be too conservative.",
                    signature=f"calibration|underconfidence|{b.bucket}",
                ))

        return findings
