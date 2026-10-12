# FixFirst

FixFirst is a community issue board for reporting local problems, ranking them by priority, and coordinating neighbors who want to help.

## Run locally

1. Create and activate a virtual environment.
2. Install the dependencies: `pip install -r requirements.txt`
3. Start the app: `python app.py`
4. Open <http://127.0.0.1:5000>.

By default, data is stored in `instance/fixfirst.db` using SQLite, so the app runs without a separate database server.

## Use MySQL

Create an empty database, install the requirements, and set `DATABASE_URL` before starting Flask:

```text
mysql+pymysql://USER:PASSWORD@HOST:3306/fixfirst
```

For example, in PowerShell:

```powershell
$env:DATABASE_URL = "mysql+pymysql://fixfirst_user:your-password@localhost:3306/fixfirst"
python app.py
```

Tables are created automatically when the app starts. Keep database credentials in environment variables; do not commit them.

## Priority scoring

Reports in the same category and location are grouped as one active issue. Each person can count once per issue; submitting a matching report increases its reported-neighbor count instead of creating a duplicate. A resolved issue can be reported again as a new issue.

Issues are ranked first by the number of unique neighbors who reported them, then by a score from 0 to 100, recalculated when the board loads:

- Severity (1–5): up to 50 points.
- Number of neighbors reporting the issue: up to 30 points, capped at 1,000 reports.
- Time waiting: up to 20 points, capped at 30 days.

The report count is calculated by the system and is not entered in the report form. The board also supports status and category filters, text search, volunteering, and status updates by a reporter or participant. Marking an issue resolved permanently deletes it and its associated reports and participants from the database, removes its card immediately, and excludes it from future board loads.

## API

- `GET /api/issues` — list issues in priority order.
- `POST /api/issues` — report an issue.
- `POST /api/issues/<id>/join` — join an initiative.
- `PATCH /api/issues/<id>/status` — update an issue status.

This starter app has no authentication. Names are used for attribution and basic participation checks, not identity verification; add authentication and authorization before using it for sensitive or high-impact decisions. The report count represents unique submitted reports, not a verified census of everyone affected.
