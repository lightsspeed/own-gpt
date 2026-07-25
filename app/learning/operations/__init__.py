"""Operations Control Plane — aggregation layer for operator workflows.

Provides 5 workspaces (Findings, Recommendations, Experiments, Decisions, Configurations)
plus the Artifact Explorer for full lineage traversal.
"""

from .router import router

__all__ = ["router"]
