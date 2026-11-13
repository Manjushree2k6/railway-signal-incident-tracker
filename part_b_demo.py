"""Part B (BCS502) demo - Q5, Q6, Q7: routing table, dispatch, exceptions, queue ordering.
Run:  python part_b_demo.py
"""
import os, tempfile
db = os.path.join(tempfile.gettempdir(), "demo_b.db")
if os.path.exists(db): os.remove(db)
os.environ["DB_PATH"] = db
import app as A
A.app.config["DB"] = db; A.init_db()
c = A.app.test_client()

print("=== Q5: routing table (30 stations / 3 divisions) ===")
for div in A.DIVISIONS:
    print(f"{div:17}", ", ".join(s for s, d in A.ROUTING.items() if d == div))
print("Handlers:", A.HANDLER); print("Priorities:", A.PRIORITY); print("Backups:", A.BACKUP)

def send(code, desc="", urg="Normal"):
    r = c.post("/api/reports", json={"reporter": "Demo", "code": code, "description": desc, "urgency": urg})
    j = r.get_json()
    print(f"{code:12} -> HTTP {r.status_code} | {j.get('status') or j.get('error')} | {j.get('route','')} | "
          f"{j.get('handler') or '-'} | {j.get('priority') or '-'} | {j.get('note') or j.get('reason') or ''}")
    return j

print("\n=== Q6/Q7: dispatch + exceptional scenarios ===")
send("AAA12-SIG01", "signal dead")                # critical -> division + Zonal HQ
send("BAA12-TRK02", "tree on track")              # critical
send("CAA12-ELE03", "short circuit")              # critical
send("AAA12-SIG04", "minor delay")                # medium, no escalation
send("ZZZ12-SIG01", "unknown station")            # unknown zone -> correction queue
send("AB12-SIG01", "malformed")                   # rejected before dispatch
send("AAA12-SIG01", "signal dead")                # duplicate
send("CAA12-ELE09", "test run", "Emergency")      # priority override
for i in range(2, 6): send(f"AAA12-SIG1{i}", "signal dead")   # capacity overflow -> backup -> queue

print("\n=== Multiple simultaneous reports: queue order (priority, then arrival) ===")
for r in c.get("/api/routing").get_json()["queue"]:
    print(r["report_id"], r["code"], r["priority"], r["note"])
print("\nStats:", c.get("/api/stats").get_json())
