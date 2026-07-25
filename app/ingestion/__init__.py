"""
Production-grade file ingestion pipeline for the RAG knowledge base.
"""

# Patch uuid_utils before any langchain import (DLL blocked by AppLocker on some systems)
import app.patch_uuid  # noqa: F401

from .config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_S,
    EXTENSION_DESCRIPTION,
    FileLock,
    IngestionConfig,
    SUPPORTED_EXTENSIONS,
)
from .models import (
    FileRecord,
    FileResult,
    FileStatus,
    PipelineReport,
    ScanDiff,
)
from .pipeline import IngestionPipeline
from .scanner import Manifest, Scanner
from .parsers import list_available, parse, register_parser

__all__ = [
    "IngestionConfig",
    "IngestionPipeline",
    "Scanner",
    "Manifest",
    "FileLock",
    "FileRecord",
    "FileResult",
    "PipelineReport",
    "ScanDiff",
    "parse",
    "list_available",
    "register_parser",
    "SUPPORTED_EXTENSIONS",
    "EXTENSION_DESCRIPTION",
]
