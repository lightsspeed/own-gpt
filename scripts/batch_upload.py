"""
Batch-upload files from a local directory through the canonical upload API.

Uploads are queued asynchronously; this script polls each job until done.

Usage:
    python scripts/batch_upload.py                           # uploads Ingest docs/
    python scripts/batch_upload.py --source-dir path/to/docs
    python scripts/batch_upload.py --source-dir path --api-url http://localhost:8000
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".txt", ".md"}

TERMINAL = {"completed", "duplicate", "failed"}


def upload_file(filepath: Path, api_url: str) -> dict | None:
    url = f"{api_url}/api/v1/documents/upload"
    with open(filepath, "rb") as f:
        resp = requests.post(url, files={"file": (filepath.name, f)}, timeout=300)
    if resp.ok:
        return resp.json()
    logger.warning("FAIL  %s — %s", filepath.name, resp.text[:200])
    return None


def wait_for_job(job_id: str, api_url: str, timeout: float = 900.0) -> dict | None:
    url = f"{api_url}/api/v1/ingestion/jobs/{job_id}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = requests.get(url, timeout=30)
        if resp.ok:
            job = resp.json()
            if job["status"] in TERMINAL:
                return job
        time.sleep(2)
    logger.warning("TIMEOUT job_id=%s", job_id)
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
    completed, failed, skipped = 0, 0, 0
    for f in files:
        result = upload_file(f, args.api_url)
        if not result:
            failed += 1
            continue
        if result["status"] == "duplicate":
            logger.info(" DUP  %s (%d chunks)", f.name, result["chunks"])
            skipped += 1
            continue
        job = wait_for_job(result["job_id"], args.api_url)
        if job is None:
            failed += 1
        elif job["status"] == "failed":
            logger.warning("FAIL  %s — %s", f.name, job["error"])
            failed += 1
        else:
            logger.info("  OK  %s (%d chunks, %d ms)", f.name, job["chunks"], job["latency_ms"])
            completed += 1

    logger.info("Done — %d ingested, %d duplicates, %d failed", completed, skipped, failed)


if __name__ == "__main__":
    main()
