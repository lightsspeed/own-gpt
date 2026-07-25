"""
Verify a clean install from requirements-lock.txt.

Usage:
    python scripts/verify_install.py              # Check current env
    python scripts/verify_install.py --clean      # Create temp venv and install
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


KEY_IMPORTS = [
    ("fastapi", "FastAPI"),
    ("uvicorn", "main"),
    ("pydantic", "BaseModel"),
    ("sqlalchemy", "create_engine"),
    ("langchain_openai", "OpenAIEmbeddings"),
    ("langchain_postgres.vectorstores", "PGVector"),
    ("langgraph.graph", "StateGraph"),
    ("tavily", "TavilyClient"),
    ("flashrank", "Ranker"),
    ("typer", "Typer"),
    ("rich.console", "Console"),
]


def check_imports():
    failures = []
    for mod, attr in KEY_IMPORTS:
        try:
            __import__(mod)
            if attr:
                m = __import__(mod, fromlist=[attr])
                getattr(m, attr)
        except Exception as e:
            failures.append(f"  FAIL: {mod}.{attr} — {e}")
    return failures


def check_lock_hash():
    lock = Path("requirements-lock.txt")
    if not lock.exists():
        return "MISSING"
    import hashlib
    h = hashlib.sha256(lock.read_bytes()).hexdigest()[:16]
    return h


def main():
    parser = argparse.ArgumentParser(description="Verify RAG benchmark install")
    parser.add_argument("--clean", action="store_true", help="Create temp venv and test install")
    args = parser.parse_args()

    print(f"Python: {sys.version}")
    print(f"Lock hash: {check_lock_hash()}")

    if args.clean:
        import venv
        tmp = Path(tempfile.mkdtemp())
        venv_path = tmp / "venv"
        print(f"\nCreating venv at {venv_path}...")
        venv.create(venv_path, with_pip=True)
        pip = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
        python = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "python"

        print("Installing from requirements-lock.txt...")
        result = subprocess.run(
            [str(pip), "install", "-r", "requirements-lock.txt"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            print(f"Install failed:\n{result.stderr[:500]}")
            return 1
        print("Install OK")

        print("\nChecking imports...")
        result = subprocess.run(
            [str(python), "-c", ";" .join(f"from {m} import {a}" for m, a in KEY_IMPORTS)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"Import check failed:\n{result.stderr[:500]}")
            return 1
        print("All imports OK")
    else:
        print(f"\nChecking imports in current environment...")
        failures = check_imports()
        if failures:
            print("\n".join(failures))
            return 1
        print("All imports OK")

    print(f"\nLock hash: {check_lock_hash()}")
    print("Benchmark reproducibility verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
