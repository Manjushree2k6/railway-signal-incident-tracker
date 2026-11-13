# P15 – Railway Signal Incident Tracker

Scenario-based project integrating **Automata Theory (BCS503)** and **Computer Networks (BCS502)** in a responsive web app.

Report submission → validation (DFA + regex) → classification (5 categories) → routing-table lookup → handler assignment / escalation to Zonal HQ → status updates → resolution.

## Stack
React 18 (frontend, served from `static/`) · Flask (backend) · SQLite (database).
> The problem statement says "MERN" in Part C item 8 but "Flask backend and SQLite database" in item 10. This repo follows item 10 (React + Flask + SQLite). Confirm with your faculty if Node/MongoDB is mandatory.

## Structure
```
app.py             Flask API + DFA/regex + classifier + routing tables + dispatch + SQLite
static/index.html  React app: Submit, My Reports, Handler, Routing, Analytics dashboards
part_a_demo.py     Q2–Q4 demo: DFA vs regex comparison, fuzz test, classification, edge cases
part_b_demo.py     Q5–Q7 demo: routing table, dispatch, exceptions, queue order
test_app.py        18 test cases (Part D)
docs/              DFA.md (diagram + transition table), ROUTING.md, TEST_CASES.md
requirements.txt, Procfile, render.yaml   deployment files
```

## Run locally
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                  # http://127.0.0.1:5000
pytest -v                      # run all tests
python part_a_demo.py          # Part A console demo
python part_b_demo.py          # Part B console demo
```
The React page loads React/Babel from cdnjs, so an internet connection is needed in the browser.

## Demo flow (Q13)
1. Submit tab: `AAA12-SIG01`, "signal dead" → validated, Signal-Failure, Critical, South Division → Zonal HQ, Signal Team.
2. Submit invalid `AB12-SIG01` → rejected with reason; `ZZZ12-SIG01` → correction queue.
3. Handler tab: select South Division – Signal Team → In Progress → Resolved.
4. My Reports: search the report ID. Routing tab: loads, queue, escalations. Analytics tab: charts.

## API
`POST /api/validate` · `POST /api/reports` · `GET /api/reports?report_id=|handler_id=|status=` · `PATCH /api/reports/<id>/status` · `GET /api/handlers` · `PATCH /api/handlers/<id>` · `GET /api/routing` · `GET /api/stats`

## Deploy (Render, free tier)
Push to GitHub → Render → New Web Service → select repo (it reads `render.yaml`). Free-tier disk is ephemeral, so SQLite data resets on redeploy; use a persistent disk or Postgres for production.

## Assumptions (confirm with faculty)
Report ID = `STATION-INCIDENT`; the 30-station list, division names, priority mapping (SIG/TRK/ELE Critical, Minor-Delay Medium, Test-Entry Low) and the classification precedence are illustrative.

## Push to GitHub
```bash
cd railway-tracker
git init && git add . && git commit -m "Railway Signal Incident Tracker"
git branch -M main
git remote add origin https://github.com/<your-username>/railway-signal-incident-tracker.git
git push -u origin main
```
