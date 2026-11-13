"""Part A (BCS503) demo - Q2, Q3, Q4: DFA vs regex, classification, edge cases.
Run:  python part_a_demo.py
"""
import random, os, tempfile
os.environ.setdefault("DB_PATH", os.path.join(tempfile.gettempdir(), "demo_a.db"))
from app import dfa_validate, regex_validate, classify

print("=== Q2: DFA vs regex ===")
codes = ["ABC12-SIG01", "XYZ45-TRK23", "DEF67-ELE89", "AB12-SIG01", "ABC1-SIG01", "ABC12-XYZ01",
         "ABC12-SIG1", "abc12-SIG01", "ABC12-SIG012", "ABC12SIG01", ""]
for c in codes:
    d, why = dfa_validate(c); r = regex_validate(c)
    print(f"{c!r:16} DFA={'Accepted' if d else 'Rejected':9} Regex={'Accepted' if r else 'Rejected':9} "
          f"{'agree' if d == r else 'MISMATCH'}  {why}")

random.seed(1)
alpha = "ABCXYZ019-SIGTRKEL abc"
bad = 0
for _ in range(50000):
    s = "".join(random.choice(alpha) for _ in range(random.randint(0, 12)))
    bad += dfa_validate(s)[0] != regex_validate(s)
for pre in ("SIG", "TRK", "ELE"):                      # also fuzz near-valid strings
    for _ in range(2000):
        s = "".join(random.choice("ABC") for _ in range(3)) + f"{random.randint(0,99):02d}-{pre}{random.randint(0,999):02d}"
        bad += dfa_validate(s)[0] != regex_validate(s)
print(f"Fuzz check (56000 strings): mismatches = {bad}")

print("\n=== Q3/Q4: classification + edge cases ===")
reports = [("ABC12-SIG01", "Signal failure"), ("ABC12-TRK02", "Track obstruction"), ("ABC12-ELE03", "Electrical fault"),
           ("ABC12-SIG04", "Minor delay reported"), ("ABC12-ELE05", "Test entry for maintenance"),
           ("ABC12-SIG06", "test of minor delay"), ("AB12-SIG01", "Signal failure"), ("ABC12-XYZ01", "Unknown")]
for code, desc in reports:
    ok, why = dfa_validate(code)
    rec = {"Report": code, "Description": desc, "Validation": "Accepted" if ok else "Rejected",
           "Category": classify(code, desc) if ok else "Not Assigned", "Reason": why}
    print(rec)
print("\nPriority rule: Test-Entry > Minor-Delay > Signal-Failure/Track-Obstruction/Electrical (by prefix).")
