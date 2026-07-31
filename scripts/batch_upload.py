"""
Batch-upload files from a local directory through the canonical upload API.

Usage:
    python scripts/batch_upload.py                           # uploads Ingest docs/
    python scripts/batch_upload.py --source-dir path/to/docs
    python scripts/batch_upload.py --source-dir path --api-url http://localhost:8000
"""

import argparse
import logging
import sys
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".txt", ".md", ".csv", ".docx", ".pptx", ".xlsx", ".htm", ".html"}


def upload_file(filepath: Path, api_url: str) -> dict | None:
    url = f"{api_url}/api/v1/documents/upload"
    with open(filepath, "rb") as f:
        resp = requests.post(url, files={"file": (filepath.name, f)}, timeout=300)
    if resp.ok:
        logger.info("  OK  %s", filepath.name)
        return resp.json()
    else:
        logger.warning("FAIL  %s — %s", filepath.name, resp.text[:200])
        return None


def main():
    parser = argparse.ArgumentParser(description="Batch-upload documents via the canonical API")
    parser.add_argument("--source-dir", default="Ingest docs", help="Directory containing files to upload")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Backend API URL")
    parser.add_argument("--recursive", action="store_true", help="Scan source-dir recursively")
    args = parser.parse_args()

    source = Path(args.source_dir)
    if not source.is_dir():
        logger.error("Source directory not found: %s", source)
        sys.exit(1)

    pattern = "**/*" if args.recursive else "*"
    files = sorted(
        p for p in source.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED
    )

    if not files:
        logger.warning("No supported files found in %s", source)
        return

    logger.info("Uploading %d file(s) from %s ...", len(files), source)
    results = []
    for f in files:
        result = upload_file(f, args.api_url)
        if result:
            results.append(result)

    logger.info("Done — %d/%d uploaded successfully", len(results), len(files))


if __name__ == "__main__":
    main()
