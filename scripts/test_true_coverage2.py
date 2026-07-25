import subprocess, time, requests, sys, json
from pathlib import Path

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

try:
    for i in range(12):
        time.sleep(2)
        try:
            r = requests.get("http://localhost:8000/docs", timeout=3)
            if r.status_code == 200:
                print(f"Backend ready after {2*(i+1)}s")
                break
        except:
            continue
    else:
        print("Backend failed")
        sys.exit(1)

    # Corpus endpoint
    r = requests.get("http://localhost:8000/api/v1/index/corpus", timeout=10)
    data = r.json()
    print(f"Corpus: {data['total_chunks']} chunks, {data['total_sources']} sources")
    chunks = data.get("chunks", [])
    if chunks:
        print(f"Sample chunk: id={chunks[0]['chunk_id'][:30]}... filename={chunks[0].get('filename', '?')}")

    # Upload a new doc with proper chunk_id
    print("\nUploading test doc...")
    test_content = b"FastAPI is a modern web framework for building APIs with Python. It uses type hints for automatic validation."
    files = {"file": ("test_cov.md", test_content, "text/markdown")}
    resp = requests.post("http://localhost:8000/api/v1/documents/upload", files=files, timeout=30)
    print(f"Upload: {resp.json()}")
    new_chunk_id = resp.json().get("chunk_id", "")

    # Verify it has chunk_id
    r = requests.get("http://localhost:8000/api/v1/index/corpus", timeout=10)
    data = r.json()
    new_chunks = [c for c in data.get("chunks", []) if c.get("filename") == "test_cov.md"]
    if new_chunks:
        print(f"New doc chunk_id={new_chunks[0]['chunk_id'][:30]} (has chunk_id in metadata: {'chunk_id' in str(new_chunks[0])})")
    else:
        print("New doc not found in corpus yet (might need index rebuild)")

    # Run benchmark to verify coverage with corpus context
    sys.path.insert(0, ".")
    from typer.testing import CliRunner
    from app.evaluation.cli import app as cli_app

    runner = CliRunner()
    result = runner.invoke(cli_app, [
        "benchmark", "thinking_fast_and_slow",
        "--workers", "2",
        "--retriever", "hybrid",
        "--ci",
    ])

    data = json.loads(result.output)
    rp = data.get("report_path", "")

    if rp:
        cf = Path(rp) / "analytics" / "retrieval_coverage.json"
        if cf.exists():
            cov = json.loads(cf.read_text())
            tc = cov.get("true_corpus_coverage", {})
            print(f"\n=== TRUE Corpus Coverage ===")
            for k in ["corpus_available", "total_corpus_chunks", "total_retrieved_unique",
                       "never_retrieved_count", "true_coverage_percent"]:
                print(f"  {k}: {tc.get(k, 'N/A')}")
            if tc.get("per_document"):
                for d in tc["per_document"]:
                    print(f"  {d['document'][:40]:40s} {d['coverage_percent']:5.1f}% ({d['retrieved_chunks']}/{d['total_chunks']})")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    proc.terminate()
    proc.wait(timeout=10)

