from pathlib import Path
from io import StringIO
import csv

base = Path("E:/NWCOURSE/High/High-Priority/own_gpt/test_ingest_src")
base.mkdir(parents=True, exist_ok=True)
(base / "subdir").mkdir(exist_ok=True)

# HTML
html = """<!DOCTYPE html>
<html><head><title>Test Document</title></head><body>
<h1>Introduction</h1><p>This is a test HTML file for the ingestion pipeline.</p>
<h2>Details</h2><p>It has multiple sections to verify section-level chunking.</p>
<h3>Sub-section</h3><p>A deeper level of content.</p>
</body></html>"""
(base / "test.html").write_text(html)

# CSV
with open(base / "test.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Name", "Role", "Department"])
    w.writerow(["Alice", "Engineer", "R&D"])
    w.writerow(["Bob", "Designer", "Product"])
    w.writerow(["Carol", "Manager", "R&D"])

# TXT in subdir
(base / "subdir" / "nested.txt").write_text("This is a nested test file to verify recursive scanning.\nIt has multiple lines of content.\n")

# Report
for p in sorted(base.rglob("*")):
    if p.is_file():
        print(f"{p.relative_to(base)}  ({p.stat().st_size} bytes)")
