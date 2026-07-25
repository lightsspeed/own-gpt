import json
from pathlib import Path

runs = sorted([d for d in Path("reports/thinking_fast_and_slow").iterdir() if d.is_dir()])
latest = runs[-1]
results = json.loads((latest / "results.json").read_text())

all_ids = set()
for r in results:
    if r.get("status") == "success":
        for c in r.get("retrieved_chunks", []):
            cid = c.get("chunk_id", "MISSING")
            all_ids.add(cid)

print(f"Unique chunk IDs in results: {len(all_ids)}")
print(f"Sample IDs (first 5):")
for cid in list(all_ids)[:5]:
    print(f"  {cid}")
