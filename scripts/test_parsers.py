import sys, re, csv
from pathlib import Path

# Test each parser directly without importing app package
def test_csv(path):
    docs = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        dialect = csv.Sniffer().sniff(f.read(8192))
        f.seek(0)
        reader = csv.reader(f, dialect)
        headers = next(reader, None)
        rows = list(reader)
    for row_num, row in enumerate(rows, start=2):
        pairs = ["{}: {}".format(h, v) for h, v in zip(headers, row) if v.strip()]
        docs.append(" | ".join(pairs))
    return docs

def test_html(path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def test_txt(path):
    return path.read_text(encoding="utf-8")

base = Path("test_ingest_src")
for p in sorted(base.rglob("*")):
    if p.is_file():
        print("{}:".format(p.name))
        if p.suffix == ".csv":
            docs = test_csv(p)
            print("  {} row(s)".format(len(docs)))
            for d in docs[:3]:
                print("    {}".format(d[:80]))
        elif p.suffix == ".html":
            text = test_html(p)
            print("  {} chars".format(len(text)))
            print("    {}".format(text[:80]))
        elif p.suffix == ".txt":
            text = test_txt(p)
            print("  {} chars".format(len(text)))
            print("    {}".format(text[:80]))
        print()
