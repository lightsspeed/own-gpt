import subprocess, time, requests, sys, json

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
        except requests.ConnectionError:
            continue
    else:
        print("Backend failed to start")
        sys.exit(1)

    r = requests.get("http://localhost:8000/api/v1/index/corpus", timeout=10)
    print(f"Status: {r.status_code}")
    try:
        data = r.json()
        print(f"Total chunks: {data.get('total_chunks', 'MISSING')}")
        print(f"Total sources: {data.get('total_sources', 'MISSING')}")
        print(f"Sources: {data.get('sources', [])}")
        chunks = data.get("chunks", [])
        if chunks:
            print(f"Sample: {json.dumps(chunks[0])}")
        print(f"\nFull response keys: {list(data.keys())}")
    except:
        print(r.text[:500])

except Exception as e:
    print(f"Error: {e}")
finally:
    proc.terminate()
    proc.wait(timeout=10)
