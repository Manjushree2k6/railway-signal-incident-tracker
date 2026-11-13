# Part D – Test Cases (18, in `test_app.py`; run `pytest -v`)

| ID | Covers | Input | Expected |
|---|---|---|---|
| T1 | Valid formats, DFA = regex | ABC12-SIG01, XYZ45-TRK23, DEF67-ELE89, AAA00-ELE99 | Both accept |
| T2 | Invalid formats, DFA = regex | "", AB12-SIG01, ABC1-SIG01, ABC12-XYZ01, ABC12-SIG1, abc12-SIG01, ABC12-SIG012, ABC12SIG01, trailing newline, non-ASCII letter, ABC12- | Both reject |
| T3 | All five categories | SIG/TRK/ELE descriptions, "Minor delay", "Test entry" | Signal-Failure, Track-Obstruction, Electrical, Minor-Delay, Test-Entry |
| T4 | Conflicting patterns | "test of minor delay"; TRK + "minor delay"; "latest contest" | Test-Entry; Minor-Delay; prefix category |
| T5 | Invalid code stored | AB12-SIG01 | Status Rejected, reason with position, stored in DB |
| T6 | Unknown zone | ZZZ12-SIG01 | Pending, Central Correction Queue |
| T7 | Critical escalation | AAA12-SIG01 | Assigned, "South Division -> Zonal HQ" |
| T8 | Non-critical | BAA12-SIG01 "minor delay" | Minor-Delay, no escalation |
| T9 | Capacity overflow | 4 Signal reports in one division | 4th goes to backup Operations Team |
| T10 | Handler unavailable, no backup | Signal + Operations unavailable | Pending (still escalated) |
| T11 | Fallback dispatch | Handler becomes available | Queued report becomes Assigned |
| T12 | Priority override | Test-Entry + Emergency | Critical + Zonal HQ, override note |
| T13 | Queue ordering (FIFO) | 3 equal-priority, capacity 1 | Earliest waiting is assigned first |
| T14 | Priority beats arrival | Low queued before Emergency | Emergency assigned first |
| T15 | Duplicate prevention | Same open report twice | HTTP 409 |
| T16 | Status updates + persistence | Assigned → Resolved; illegal jump | Illegal = 400; new client reads Resolved from DB |
| T17 | Inline validation API | /api/validate | DFA, regex agree + category + zone |
| T18 | Routing table | 30 stations, 3 divisions | Exactly 30 / 3 |
