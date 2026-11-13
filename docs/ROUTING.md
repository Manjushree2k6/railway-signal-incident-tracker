# Part B – Routing / Dispatch (BCS502)

## Station → division (key = first 3 characters of the validated report ID)
| Division | Station keys |
|---|---|
| South Division | AAA … AAJ |
| Central Division | BAA … BAJ |
| North Division | CAA … CAJ |

*The paper gives no official list, so this mapping is illustrative. Edit `DIVISIONS` in `app.py` to use the official one.*

## Category → handler / priority / routing
| Category | Handler | Priority | Route |
|---|---|---|---|
| Signal-Failure | Signal Team | Critical | Division → **Zonal HQ** |
| Track-Obstruction | Track Team | Critical | Division → **Zonal HQ** |
| Electrical | Electrical Team | Critical | Division → **Zonal HQ** |
| Minor-Delay | Operations Team | Medium | Division |
| Test-Entry | Testing Team | Low | Division |

Backup handlers: Signal / Track / Electrical → Operations Team; Operations → Testing; Testing → Operations.
Each division has its own copy of every team (15 handlers, default capacity 3).

## Dispatch algorithm (`submit()` / `try_assign()` / `drain()`)
1. Validate (DFA); reject malformed IDs with a reason (still stored).
2. Reject duplicates of an open report (HTTP 409).
3. Classify, get priority (urgency = *Emergency* overrides to Critical).
4. Extract routing key **only after validation**; look up division. Unknown key → *Central Correction Queue* (Pending).
5. Check handler availability and capacity; else try backup handler in the same division; else stay **Pending** in the waiting queue.
6. Critical → route "Division → Zonal HQ" (kept even while queued).
7. Record route, priority, timestamp, status. Statuses: **Pending → Assigned → In Progress → Resolved**.
8. On Resolved (or when a handler's availability/capacity changes) the queue is re-dispatched in order **priority (Critical, Medium, Low), then arrival (FIFO)**.

## Exceptional scenarios
| Scenario | Behaviour |
|---|---|
| Unknown zone / key | Central Correction Queue |
| Malformed identifier | Rejected before dispatch, reason shown |
| Handler unavailable / capacity exceeded | Backup handler, else waiting queue |
| Priority override | Emergency urgency → Critical + Zonal HQ |
| Simultaneous reports | Deterministic order (priority, FIFO); duplicates blocked; SQLite UNIQUE report_id |
