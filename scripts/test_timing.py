import json, time, urllib.request

BASE = "http://127.0.0.1:8000"

def converse(message, session_id=""):
    payload = json.dumps({"message": message, "session_id": session_id}).encode()
    req = urllib.request.Request(
        f"{BASE}/converse", data=payload,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data, time.time() - t0

r1, t1 = converse("my vehicle tyre bursts all the time")
print(f"Turn 1: {t1:.2f}s | type={r1['type']}")

r2, t2 = converse("Yes sidewall has visible bulges", r1["session_id"])
print(f"Turn 2: {t2:.2f}s | type={r2['type']}")

r3, t3 = converse("It happens on highways at high speed", r1["session_id"])
print(f"Turn 3: {t3:.2f}s | type={r3['type']}")

print(f"Total: {t1+t2+t3:.2f}s")
