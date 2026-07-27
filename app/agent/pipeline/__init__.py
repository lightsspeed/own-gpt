import os
from typing import Any, Dict

import yaml

from .pipeline import RAGPipeline, PipelineContext
from .intent import IntentClassifier, IntentResult, Intent
from .router import RequestRouter, RouterResult, RouteDecision
from .planner import Planner, SourcePolicyResult
from .evidence_builder import EvidenceBuilder, EvidenceBuilderResult
from .rewrite import QueryRewriter, RewriteResult
from .retriever import Retriever, RetrievedChunk
from .reranker import CrossEncoderReranker, RankedChunk
from .confidence import ConfidenceEvaluator, ConfidenceResult
from .validation import ResponseValidator, ValidationResult
from .tracing import TracingService, PipelineTrace


def load_pipeline_config(path: str | None = None) -> Dict[str, Any]:
    """Load pipeline configuration from YAML. Returns empty dict on failure."""
    if path is None:
        path = os.environ.get(
            "PIPELINE_CONFIG",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "pipeline_config.yaml",
            ),
        )
    try:
        with open(path) as f:
            cfg = yaml.safe_load(f)
            return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


__all__ = [
    "RAGPipeline",
    "PipelineContext",
    "IntentClassifier",
    "IntentResult",
    "Intent",
    "RequestRouter",
    "RouterResult",
    "RouteDecision",
    "Planner",
    "SourcePolicyResult",
    "EvidenceBuilder",
    "EvidenceBuilderResult",
    "QueryRewriter",
    "RewriteResult",
    "Retriever",
    "RetrievedChunk",
    "CrossEncoderReranker",
    "RankedChunk",
    "ConfidenceEvaluator",
    "ConfidenceResult",
    "ResponseValidator",
    "ValidationResult",
    "TracingService",
    "PipelineTrace",
]
