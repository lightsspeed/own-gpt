import http.client, json

body = json.dumps({"message": "Who is the main protagonist of The Secret Garden?", "session_id": "test-sources-clean-1"})
conn = http.client.HTTPConnection("localhost", 8000, timeout=60)
conn.request("POST", "/api/v1/chat/stream", body, {"Content-Type": "application/json"})
resp = conn.getresponse()
raw = resp.read().decode()
conn.close()

for line in raw.split("\n"):
    line = line.strip()
    if line.startswith("data: ") and line[6:] != "[DONE]":
        try:
            p = json.loads(line[6:])
            if p.get("type") == "resources":
                print("Sources shown in UI:")
                for r in p.get("resources", []):
                    print("  {}: {}".format(r.get("type","?"), r.get("title","?")[:80]))
            elif p.get("type") == "content":
                content = p.get("content","")
                if len(content) > 5:
                    print("Answer begins: {}...".format(content[:60]))
        except:
            pass
