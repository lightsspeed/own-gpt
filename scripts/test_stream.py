import http.client, json

conn = http.client.HTTPConnection("localhost", 8000, timeout=60)
body = json.dumps({"message": "What is terraform state?", "session_id": "test-sources-5"})
conn.request("POST", "/api/v1/chat/stream", body, {"Content-Type": "application/json"})
resp = conn.getresponse()
raw = resp.read().decode()
conn.close()

for line in raw.split("\n"):
    line = line.strip()
    if line.startswith("data: ") and line[6:] != "[DONE]":
        try:
            p = json.loads(line[6:])
            if p.get("type") in ("resources", "content"):
                print("Event type: {}".format(p.get("type")))
                if p.get("type") == "resources":
                    print("  Resources count: {}".format(len(p.get("resources", []))))
                    for i, r in enumerate(p.get("resources", [])[:3]):
                        print("  [{}] type={} title={}".format(i, r.get("type","?"), r.get("title","?")[:80]))
                elif p.get("type") == "content":
                    print("  Content: {}...".format(p.get("content","")[:80]))
        except Exception as e:
            print("Parse error: {} on line: {}...".format(e, line[:100]))
