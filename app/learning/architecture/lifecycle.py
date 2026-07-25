"""
Lifecycle stages for the optimization pipeline.

Every artifact belongs to exactly one stage:
    OBSERVE → MEASURE → EXPLAIN → PROPOSE → VALIDATE → APPLY
"""

from __future__ import annotations

from enum import Enum


class LifecycleStage(str, Enum):
    OBSERVE = "observe"
    MEASURE = "measure"
    EXPLAIN = "explain"
    PROPOSE = "propose"
    VALIDATE = "validate"
    APPLY = "apply"
