import pytest
import app as A

VALID = ["ABC12-SIG01", "XYZ45-TRK23", "DEF67-ELE89", "AAA00-ELE99"]
INVALID = ["", "AB12-SIG01", "ABC1-SIG01", "ABC12-XYZ01", "ABC12-SIG1", "abc12-SIG01",
           "ABC12-SIG012", "ABC12SIG01", "ABC12-SIG01\n", "ÀBC12-SIG01", "ABC12-"]

@pytest.fixture
def c(tmp_path):
    A.app.config["DB"] = str(tmp_path / "t.db"); A.init_db()
    return A.app.test_client()

def post(c, code, desc="", urg="Normal"):
    r = c.post("/api/reports", json={"reporter": "SM", "code": code, "description": desc, "urgency": urg})
    return r.status_code, r.get_json()

def hid(c, div, team):
    return next(h["id"] for h in c.get("/api/handlers").get_json() if h["division"] == div and h["team"] == team)

def setup_h(c, div, team, **kw): c.patch(f"/api/handlers/{hid(c, div, team)}", json=kw)
def advance(c, rid):
    for s in ("In Progress", "Resolved"): c.patch(f"/api/reports/{rid}/status", json={"status": s})

# T1-T2: valid / invalid formats, DFA == regex
@pytest.mark.parametrize("code", VALID)
def test_T1_valid_dfa_regex_agree(code):
    assert A.dfa_validate(code)[0] is True and A.regex_validate(code) is True

@pytest.mark.parametrize("code", INVALID)
def test_T2_invalid_dfa_regex_agree(code):
    assert A.dfa_validate(code)[0] is False and A.regex_validate(code) is False

# T3: all five categories
@pytest.mark.parametrize("code,desc,cat", [
    ("ABC12-SIG01", "signal dead", "Signal-Failure"), ("ABC12-TRK02", "tree on line", "Track-Obstruction"),
    ("ABC12-ELE03", "short circuit", "Electrical"), ("ABC12-SIG04", "Minor delay reported", "Minor-Delay"),
    ("ABC12-ELE05", "Test entry", "Test-Entry")])
def test_T3_five_categories(code, desc, cat): assert A.classify(code, desc) == cat

# T4: conflicting patterns -> documented priority Test > Minor-Delay > prefix
def test_T4_conflict_priority():
    assert A.classify("ABC12-SIG01", "test of minor delay") == "Test-Entry"
    assert A.classify("ABC12-TRK01", "minor delay near yard") == "Minor-Delay"
    assert A.classify("ABC12-SIG01", "latest contest result") == "Signal-Failure"  # no false 'test' match

def test_T5_invalid_rejected_with_reason_and_stored(c):
    code, r = post(c, "AB12-SIG01", "x")
    assert r["status"] == "Rejected" and "position" in r["reason"] and r["handler"] is None
    assert c.get("/api/reports?report_id=" + r["report_id"]).get_json()[0]["validation"] == "Rejected"

def test_T6_unknown_zone_goes_to_correction_queue(c):
    _, r = post(c, "ZZZ12-SIG01", "x")
    assert r["status"] == "Pending" and r["route"] == "Central Correction Queue" and r["handler"] is None

def test_T7_critical_escalates_to_zonal_hq(c):
    _, r = post(c, "AAA12-SIG01", "signal dead")
    assert r["status"] == "Assigned" and r["route"] == "South Division -> Zonal HQ" and r["escalated"] == 1

def test_T8_noncritical_no_escalation(c):
    _, r = post(c, "BAA12-SIG01", "minor delay")
    assert r["category"] == "Minor-Delay" and r["route"] == "Central Division" and r["escalated"] == 0

def test_T9_capacity_overflow_uses_backup(c):
    for i in range(4): _, r = post(c, f"AAA12-SIG0{i}", "dead")
    assert r["handler"] == "Operations Team" and "Backup" in r["note"]

def test_T10_unavailable_and_no_backup_queues_then_T11_drains(c):
    for t in ("Signal Team", "Operations Team"): setup_h(c, "South Division", t, available=False)
    _, r = post(c, "AAA12-SIG01", "dead")
    assert r["status"] == "Pending" and r["escalated"] == 1       # critical still escalated while queued
    setup_h(c, "South Division", "Signal Team", available=True)   # T11: fallback dispatch after recovery
    assert c.get("/api/reports?report_id=" + r["report_id"]).get_json()[0]["status"] == "Assigned"

def test_T12_priority_override_emergency(c):
    _, r = post(c, "CAA12-SIG01", "test run", urg="Emergency")
    assert r["priority"] == "Critical" and "override" in r["note"] and r["route"].endswith("Zonal HQ")

def test_T13_fifo_queue_ordering(c):
    setup_h(c, "North Division", "Signal Team", capacity=1); setup_h(c, "North Division", "Operations Team", available=False)
    ids = [post(c, f"CAA12-SIG0{i}", "d")[1]["report_id"] for i in range(3)]
    advance(c, ids[0])
    st = {i: c.get("/api/reports?report_id=" + i).get_json()[0]["status"] for i in ids}
    assert st[ids[1]] == "Assigned" and st[ids[2]] == "Pending"

def test_T14_priority_beats_arrival_in_queue(c):
    setup_h(c, "South Division", "Testing Team", capacity=1); setup_h(c, "South Division", "Operations Team", available=False)
    first = post(c, "AAA12-ELE01", "test a")[1]["report_id"]
    low = post(c, "AAA12-ELE02", "test b")[1]["report_id"]
    emerg = post(c, "AAA12-ELE03", "test c", urg="Emergency")[1]["report_id"]
    advance(c, first)
    get = lambda i: c.get("/api/reports?report_id=" + i).get_json()[0]["status"]
    assert get(emerg) == "Assigned" and get(low) == "Pending"

def test_T15_duplicate_not_assigned_twice(c):
    assert post(c, "AAA12-SIG01", "dead")[0] == 201
    assert post(c, "AAA12-SIG01", "dead")[0] == 409

def test_T16_status_transitions_and_persistence(c):
    _, r = post(c, "AAA12-TRK01", "obstruction")
    rid = r["report_id"]
    assert c.patch(f"/api/reports/{rid}/status", json={"status": "Resolved"}).status_code == 400
    advance(c, rid)
    fresh = A.app.test_client()   # new client, same DB file -> data persisted
    assert fresh.get("/api/reports?report_id=" + rid).get_json()[0]["status"] == "Resolved"
    s = fresh.get("/api/stats").get_json()
    assert s["resolved"] == 1 and s["unresolved"] == 0

def test_T17_validate_endpoint_inline_feedback(c):
    j = c.post("/api/validate", json={"code": "ABC12-ELE01", "description": "x"}).get_json()
    assert j["agree"] and j["dfa"] and j["category"] == "Electrical" and "Unknown" in j["division"]

def test_T18_thirty_stations_three_divisions():
    assert len(A.ROUTING) == 30 and len(set(A.ROUTING.values())) == 3
