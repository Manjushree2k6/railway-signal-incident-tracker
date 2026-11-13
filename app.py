import re, os, uuid, sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, g

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["DB"] = os.environ.get("DB_PATH", "tracker.db")

# ---------------- Part A: DFA + regex + classification ----------------
PATTERN = re.compile(r"[A-Z]{3}[0-9]{2}-(SIG|TRK|ELE)[0-9]{2}")
def regex_validate(code): return PATTERN.fullmatch(code) is not None

T = {"q0": [("L", "q1")], "q1": [("L", "q2")], "q2": [("L", "q3")],
     "q3": [("D", "q4")], "q4": [("D", "q5")], "q5": [("-", "q6")],
     "q6": [("S", "q7"), ("T", "q12"), ("E", "q17")],
     "q7": [("I", "q8")], "q8": [("G", "q9")], "q9": [("D", "q10")], "q10": [("D", "q11")],
     "q12": [("R", "q13")], "q13": [("K", "q14")], "q14": [("D", "q15")], "q15": [("D", "q16")],
     "q17": [("L", "q18")], "q18": [("E", "q19")], "q19": [("D", "q20")], "q20": [("D", "q21")]}
FINAL = {"q11", "q16", "q21"}
HINT = {"q0": "an uppercase letter (station code)", "q1": "an uppercase letter (station code)",
        "q2": "an uppercase letter (station code)", "q3": "a digit (station code)",
        "q4": "a digit (station code)", "q5": "'-' separator", "q6": "S, T or E (prefix SIG/TRK/ELE)",
        "q7": "'I' (SIG)", "q8": "'G' (SIG)", "q12": "'R' (TRK)", "q13": "'K' (TRK)",
        "q17": "'L' (ELE)", "q18": "'E' (ELE)"}
for s in ("q9", "q10", "q14", "q15", "q19", "q20"): HINT[s] = "a digit (incident number)"
for s in FINAL: HINT[s] = "end of input (extra characters)"

def _match(sym, ch):
    if sym == "L": return "A" <= ch <= "Z"
    if sym == "D": return "0" <= ch <= "9"
    return ch == sym

def dfa_validate(code):
    """Returns (accepted, reason). Any bad symbol -> trap state qT (absorbing)."""
    s = "q0"
    for i, ch in enumerate(code):
        prev = s
        s = next((n for sym, n in T.get(s, []) if _match(sym, ch)), "qT")
        if s == "qT":
            return False, f"Invalid character {ch!r} at position {i+1}: expected {HINT[prev]}"
    if s in FINAL: return True, ""
    return False, "Incomplete identifier: expected format ABC12-SIG01 (SIG/TRK/ELE + 2 digits)"

def classify(code, desc):
    d = (desc or "").lower()
    if re.search(r"\btest(s|ing)?\b", d): return "Test-Entry"      # priority 1
    if "minor delay" in d: return "Minor-Delay"                    # priority 2
    return {"SIG": "Signal-Failure", "TRK": "Track-Obstruction", "ELE": "Electrical"}[code[6:9]]  # 3

# ---------------- Part B: routing tables ----------------
DIVISIONS = {"South Division": "AA", "Central Division": "BA", "North Division": "CA"}
ROUTING = {pre + chr(65 + i): div for div, pre in DIVISIONS.items() for i in range(10)}  # 30 stations
HANDLER = {"Signal-Failure": "Signal Team", "Track-Obstruction": "Track Team", "Electrical": "Electrical Team",
           "Minor-Delay": "Operations Team", "Test-Entry": "Testing Team"}
PRIORITY = {"Signal-Failure": "Critical", "Track-Obstruction": "Critical", "Electrical": "Critical",
            "Minor-Delay": "Medium", "Test-Entry": "Low"}
BACKUP = {"Signal Team": "Operations Team", "Track Team": "Operations Team", "Electrical Team": "Operations Team",
          "Operations Team": "Testing Team", "Testing Team": "Operations Team"}
ORDER = "CASE priority WHEN 'Critical' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, id"  # priority, then FIFO

# ---------------- Database ----------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS handlers(id INTEGER PRIMARY KEY, division TEXT, team TEXT,
  available INTEGER DEFAULT 1, capacity INTEGER DEFAULT 3, load INTEGER DEFAULT 0, UNIQUE(division, team));
CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT, report_id TEXT UNIQUE, reporter TEXT,
  code TEXT, description TEXT, urgency TEXT, validation TEXT, reason TEXT, category TEXT, priority TEXT,
  division TEXT, handler_id INTEGER, route TEXT, escalated INTEGER DEFAULT 0, status TEXT,
  note TEXT DEFAULT '', created_at TEXT, updated_at TEXT);"""

def init_db():
    d = sqlite3.connect(app.config["DB"]); d.executescript(SCHEMA)
    for div in DIVISIONS:
        for t in set(HANDLER.values()):
            d.execute("INSERT OR IGNORE INTO handlers(division,team) VALUES(?,?)", (div, t))
    d.commit(); d.close()

def db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB"]); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def _close(_):
    d = g.pop("db", None)
    if d: d.close()

now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
REP = "SELECT r.*, h.team AS handler FROM reports r LEFT JOIN handlers h ON h.id=r.handler_id "
rows = lambda sql, a=(): [dict(r) for r in db().execute(sql, a).fetchall()]

# ---------------- Dispatch ----------------
def try_assign(r):
    """Check availability + capacity of the primary handler, then the backup (same division)."""
    team = HANDLER[r["category"]]
    for t in (team, BACKUP[team]):
        h = db().execute("SELECT * FROM handlers WHERE division=? AND team=?", (r["division"], t)).fetchone()
        if h and h["available"] and h["load"] < h["capacity"]:
            db().execute("UPDATE handlers SET load=load+1 WHERE id=?", (h["id"],))
            note = r["note"] + ("" if t == team else f" Backup handler used ({t}).")
            db().execute("UPDATE reports SET handler_id=?, status='Assigned', note=?, updated_at=? WHERE id=?",
                         (h["id"], note.strip(), now(), r["id"]))
            return True
    return False

def drain():
    for r in rows(f"SELECT * FROM reports WHERE status='Pending' AND division IS NOT NULL ORDER BY {ORDER}"):
        try_assign(r)

def submit(data):
    code = (data.get("code") or "").strip(); desc = (data.get("description") or "").strip()
    urgency = data.get("urgency", "Normal")
    ok, reason = dfa_validate(code)
    if ok and db().execute("SELECT 1 FROM reports WHERE code=? AND description=? AND status IN "
                           "('Pending','Assigned','In Progress')", (code, desc)).fetchone():
        return {"error": "Duplicate open report: not assigned again."}, 409
    rec = dict(report_id="RPT-" + uuid.uuid4().hex[:8].upper(), reporter=data.get("reporter", ""), code=code,
               description=desc, urgency=urgency, created_at=now(), updated_at=now(), note="")
    if not ok:   # rejected before dispatch, but still stored
        rec.update(validation="Rejected", reason=reason, category="Not Assigned", route="Rejected before dispatch",
                   status="Rejected")
    else:
        cat = classify(code, desc); prio = PRIORITY[cat]
        if urgency == "Emergency" and prio != "Critical":
            prio = "Critical"; rec["note"] = "Priority override: Emergency urgency."
        div = ROUTING.get(code[:3])
        esc = int(prio == "Critical")
        if div is None:
            route = "Central Correction Queue"; rec["note"] = (rec["note"] + " Unknown station key.").strip()
        else:
            route = div + (" -> Zonal HQ" if esc else "")
        rec.update(validation="Accepted", reason="", category=cat, priority=prio, division=div, route=route,
                   escalated=esc if div else 0, status="Pending")
    cols = ",".join(rec)
    cur = db().execute(f"INSERT INTO reports({cols}) VALUES({','.join('?' * len(rec))})", list(rec.values()))
    if rec["status"] == "Pending" and rec["division"]:
        try_assign(dict(db().execute("SELECT * FROM reports WHERE id=?", (cur.lastrowid,)).fetchone()))
    db().commit()
    return rows(REP + "WHERE r.id=?", (cur.lastrowid,))[0], 201

# ---------------- API ----------------
@app.get("/")
def index(): return app.send_static_file("index.html")

@app.post("/api/validate")
def api_validate():
    d = request.get_json(force=True); code = (d.get("code") or "").strip()
    ok, reason = dfa_validate(code); rx = regex_validate(code)
    out = dict(dfa=ok, regex=rx, agree=ok == rx, reason=reason)
    if ok:
        cat = classify(code, d.get("description", "")); p = PRIORITY[cat]
        if d.get("urgency") == "Emergency": p = "Critical"
        out.update(category=cat, priority=p, division=ROUTING.get(code[:3], "Unknown (correction queue)"))
    return jsonify(out)

@app.post("/api/reports")
def api_submit():
    out, code = submit(request.get_json(force=True)); return jsonify(out), code

@app.get("/api/reports")
def api_reports():
    sql, a = REP + "WHERE 1=1", []
    for k, col in (("report_id", "r.report_id"), ("handler_id", "r.handler_id"), ("status", "r.status")):
        if request.args.get(k): sql += f" AND {col}=?"; a.append(request.args[k])
    return jsonify(rows(sql + f" ORDER BY {ORDER}", a))

NEXT = {"Assigned": "In Progress", "In Progress": "Resolved"}
@app.patch("/api/reports/<rid>/status")
def api_status(rid):
    new = request.get_json(force=True).get("status")
    r = db().execute("SELECT * FROM reports WHERE report_id=?", (rid,)).fetchone()
    if not r: return jsonify(error="Not found"), 404
    if NEXT.get(r["status"]) != new:
        return jsonify(error=f"Illegal transition {r['status']} -> {new}"), 400
    db().execute("UPDATE reports SET status=?, updated_at=? WHERE id=?", (new, now(), r["id"]))
    if new == "Resolved":
        db().execute("UPDATE handlers SET load=MAX(load-1,0) WHERE id=?", (r["handler_id"],)); drain()
    db().commit(); return jsonify(rows(REP + "WHERE r.id=?", (r["id"],))[0])

@app.get("/api/handlers")
def api_handlers(): return jsonify(rows("SELECT * FROM handlers ORDER BY id"))

@app.patch("/api/handlers/<int:hid>")
def api_handler(hid):
    d = request.get_json(force=True)
    if "available" in d: db().execute("UPDATE handlers SET available=? WHERE id=?", (int(bool(d["available"])), hid))
    if "capacity" in d: db().execute("UPDATE handlers SET capacity=? WHERE id=?", (max(int(d["capacity"]), 0), hid))
    drain(); db().commit()
    return jsonify(rows("SELECT * FROM handlers WHERE id=?", (hid,))[0])

@app.get("/api/routing")
def api_routing():
    return jsonify(routing=[{"station": s, "division": d} for s, d in ROUTING.items()],
                   handler_table=HANDLER, priority_table=PRIORITY,
                   handlers=rows("SELECT * FROM handlers ORDER BY id"),
                   queue=rows(REP + f"WHERE r.status='Pending' ORDER BY {ORDER}"),
                   decisions=rows(REP + "WHERE r.escalated=1 OR r.note!='' ORDER BY r.id DESC LIMIT 50"))

@app.get("/api/stats")
def api_stats():
    c = lambda col, w="status!='Rejected'": {r[0] or "Unrouted": r[1] for r in
        db().execute(f"SELECT {col}, COUNT(*) FROM reports WHERE {w} GROUP BY {col}")}
    st = c("status", "1=1")
    return jsonify(total=sum(st.values()), pending=st.get("Pending", 0), assigned=st.get("Assigned", 0),
                   in_progress=st.get("In Progress", 0), resolved=st.get("Resolved", 0),
                   rejected=st.get("Rejected", 0), by_zone=c("division"), by_category=c("category"),
                   unresolved=sum(v for k, v in st.items() if k in ("Pending", "Assigned", "In Progress")))

init_db()
if __name__ == "__main__":
    app.run(debug=True)
