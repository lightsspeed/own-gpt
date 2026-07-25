"""
Ingest a corpus document set into the RAG pipeline.

Usage:
    python scripts/ingest_corpus.py fastapi --api-url http://localhost:8000
    python scripts/ingest_corpus.py kubernetes --api-url http://localhost:8000
    python scripts/ingest_corpus.py terraform --api-url http://localhost:8000
    python scripts/ingest_corpus.py aws_well_architected --api-url http://localhost:8000
    python scripts/ingest_corpus.py all --api-url http://localhost:8000
"""

import argparse
import logging
import os
import sys
import tempfile
import urllib.request
import zipfile
import io
import shutil
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Corpus definitions ─────────────────────────────────────────────────────

CORPORA = {}

# ---- FastAPI ----
FASTAPI_DOCS_URL = (
    "https://github.com/fastapi/fastapi/archive/refs/heads/master.zip"
)
FASTAPI_DOCS_DIR = "fastapi-master/docs/en/docs"

CORPORA["fastapi"] = {
    "label": "FastAPI",
    "source_url": FASTAPI_DOCS_URL,
    "archive_docs_dir": FASTAPI_DOCS_DIR,
    "file_pattern": "*.md",
    "description": "FastAPI official documentation (tutorial, usage guide, deployment)",
    "filenames": ["fastapi_intro.md", "fastapi_tutorial.md"],
}

# ---- Kubernetes ----
K8S_DOCS_URL = (
    "https://github.com/kubernetes/website/archive/refs/heads/main.zip"
)
K8S_DOCS_DIR = "website-main/content/en/docs"

CORPORA["kubernetes"] = {
    "label": "Kubernetes",
    "source_url": K8S_DOCS_URL,
    "archive_docs_dir": K8S_DOCS_DIR,
    "file_pattern": "*.md",
    "description": "Kubernetes official documentation (concepts, tasks, reference)",
    "filenames": ["kubernetes_concepts.md", "kubernetes_tasks.md"],
}

# ---- Terraform ----
TERRAFORM_DOCS_URL = (
    "https://github.com/hashicorp/terraform/archive/refs/heads/main.zip"
)
TERRAFORM_DOCS_DIR = "terraform-main/website/docs"

CORPORA["terraform"] = {
    "label": "Terraform",
    "source_url": TERRAFORM_DOCS_URL,
    "archive_docs_dir": TERRAFORM_DOCS_DIR,
    "file_pattern": "*.md",
    "description": "Terraform by HashiCorp official documentation (language, CLI, providers)",
    "filenames": ["terraform_intro.md", "terraform_language.md"],
}

# ---- AWS Well-Architected Framework ----
AWS_WAF_URL = (
    "https://docs.aws.amazon.com/pdfs/wellarchitected/latest/framework/"
    "wellarchitected-framework.pdf"
)

CORPORA["aws_well_architected"] = {
    "label": "AWS Well-Architected Framework",
    "source_url": AWS_WAF_URL,
    "archive_docs_dir": None,
    "file_pattern": None,
    "description": "AWS Well-Architected Framework (pillars, best practices, design principles)",
    "filenames": ["aws_well_architected_framework.pdf"],
}


# ── Helpers ────────────────────────────────────────────────────────────────

def _download_zip(url: str, extract_subdir: str, file_pattern: str) -> list[Path]:
    """Download a ZIP from GitHub, extract matching files, return list of temp paths."""
    logger.info("Downloading %s ...", url)
    resp = urllib.request.urlopen(url)
    zip_data = resp.read()
    tmp_dir = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        zf.extractall(tmp_dir)
    docs_dir = tmp_dir / extract_subdir
    if not docs_dir.exists():
        logger.warning("Expected docs dir %s not found, searching...", docs_dir)
        # fallback: search recursively
        files = list(tmp_dir.rglob(file_pattern))
    else:
        files = list(docs_dir.rglob(file_pattern))
    logger.info("Found %d matching files in archive", len(files))
    return files


def _download_pdf(url: str) -> Path:
    """Download a PDF, return temp path."""
    logger.info("Downloading %s ...", url)
    tmp = Path(tempfile.mktemp(suffix=".pdf"))
    urllib.request.urlretrieve(url, tmp)
    logger.info("Downloaded PDF to %s", tmp)
    return tmp


def _upload_file(filepath: Path, api_url: str, display_name: str = "") -> dict:
    """Upload a file to the RAG document ingestion API."""
    url = f"{api_url}/api/v1/documents/upload"
    filename = display_name or filepath.name
    with open(filepath, "rb") as f:
        resp = requests.post(url, files={"file": (filename, f)}, timeout=300)
    resp.raise_for_status()
    return resp.json()


def _merge_markdown_files(files: list[Path], output: Path):
    """Concatenate multiple markdown files into one for batch upload."""
    seen = set()
    with open(output, "w", encoding="utf-8") as out:
        for fpath in sorted(files, key=lambda p: str(p)):
            key = fpath.name
            if key in seen:
                continue
            seen.add(key)
            content = fpath.read_text(encoding="utf-8", errors="replace")
            out.write(f"\n\n<!-- source: {fpath.relative_to(fpath.parents[3] if len(fpath.parents) > 3 else fpath.parent)} -->\n\n")
            out.write(content)
    logger.info("Merged %d files into %s", len(seen), output)


# ── Ingest ─────────────────────────────────────────────────────────────────

def ingest_fastapi(api_url: str):
    files = _download_zip(FASTAPI_DOCS_URL, FASTAPI_DOCS_DIR, "*.md")

    # Filter to key tutorial/guide docs
    key_dirs = {"tutorial", "guide", "deployment", "advanced", "features"}
    selected = [f for f in files if any(d in f.parts for d in key_dirs)]
    if not selected:
        selected = files[:50]

    tmp_md = Path(tempfile.mktemp(suffix=".md"))
    _merge_markdown_files(selected, tmp_md)
    result = _upload_file(tmp_md, api_url, display_name="fastapi_docs.md")
    logger.info("FastAPI ingested: %s", result)
    return result


def ingest_kubernetes(api_url: str):
    files = _download_zip(K8S_DOCS_URL, K8S_DOCS_DIR, "*.md")

    # Focus on key concept docs
    key_prefixes = {"concepts/", "tasks/", "setup/"}
    selected = []
    for f in files:
        rel = str(f.relative_to(f.parents[0]))
        if any(rel.startswith(p) for p in key_prefixes):
            selected.append(f)

    if not selected:
        selected = files[:80]

    tmp_md = Path(tempfile.mktemp(suffix=".md"))
    _merge_markdown_files(selected, tmp_md)
    result = _upload_file(tmp_md, api_url, display_name="kubernetes_docs.md")
    logger.info("Kubernetes ingested: %s", result)
    return result


def ingest_terraform(api_url: str):
    files = _download_zip(TERRAFORM_DOCS_URL, TERRAFORM_DOCS_DIR, "*.md")

    key_dirs = {"language", "cli", "intro"}
    selected = [f for f in files if any(d in f.parts for d in key_dirs)]
    if not selected:
        selected = files[:50]

    tmp_md = Path(tempfile.mktemp(suffix=".md"))
    _merge_markdown_files(selected, tmp_md)
    result = _upload_file(tmp_md, api_url, display_name="terraform_docs.md")
    logger.info("Terraform ingested: %s", result)
    return result


def ingest_aws_well_architected(api_url: str):
    pdf_path = _download_pdf(AWS_WAF_URL)
    result = _upload_file(pdf_path, api_url, display_name="aws_well_architected_framework.pdf")
    logger.info("AWS Well-Architected ingested: %s", result)
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────

INGEST_FUNCS = {
    "fastapi": ingest_fastapi,
    "kubernetes": ingest_kubernetes,
    "terraform": ingest_terraform,
    "aws_well_architected": ingest_aws_well_architected,
}


def main():
    parser = argparse.ArgumentParser(description="Ingest a corpus into the RAG pipeline")
    parser.add_argument(
        "corpus",
        choices=list(INGEST_FUNCS.keys()) + ["all"],
        help="Corpus to ingest, or 'all' for all four",
    )
    parser.add_argument("--api-url", default="http://localhost:8000", help="Backend API base URL")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild Whoosh index after ingestion")
    args = parser.parse_args()

    if args.corpus == "all":
        results = {}
        for name, func in INGEST_FUNCS.items():
            try:
                results[name] = func(args.api_url)
            except Exception as e:
                logger.error("Failed to ingest %s: %s", name, e)
                results[name] = {"error": str(e)}
    else:
        results = {args.corpus: INGEST_FUNCS[args.corpus](args.api_url)}

    print("\n=== Ingestion Results ===")
    for name, result in results.items():
        status = result.get("message", result.get("error", "unknown"))
        print(f"  {name}: {status}")

    if args.rebuild_index:
        logger.info("Rebuilding Whoosh index...")
        resp = requests.post(f"{args.api_url}/api/v1/index/rebuild")
        logger.info("Index rebuild: %s", resp.json())


if __name__ == "__main__":
    main()
