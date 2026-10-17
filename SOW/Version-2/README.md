# SOW Project Workspace (Flask + SQLAlchemy)

A starter web app based on the SOW screenshots: project details, cost/billing, resource planning, milestones, scope, risks, skills, software requirements and declarations. It uses prefilled demo data; users can edit it, submit, save the record, and open a print-ready SOW that can be printed or saved as PDF.

## Requirements
- Python 3.10+
- SQL Server + Microsoft ODBC Driver 18 for SQL Server for the MSSQL setup
- Or use SQLite for the local demo

## Run locally (SQLite demo)
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. SQLite creates the database in `instance/sow_demo.db` automatically when the app starts. The ZIP includes a pre-populated SQLite demo database with one sample project, three resources and four milestones. To seed a fresh database, run `python seed_demo.py`.

## Connect to Microsoft SQL Server
1. Install Microsoft ODBC Driver 18 for SQL Server.
2. Copy `.env.example` to `.env`.
3. Set `DATABASE_URL` to your SQL Server database connection URL. URL-encode special characters in SQL credentials.
4. Load environment variables before running. Easiest: use `python-dotenv` by adding these lines near the top of `app.py`:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```
   Or set environment variables in your terminal / IDE run configuration.
5. Ensure the SQL Server database already exists and the login has permission to create tables.
6. Run `python app.py`. `db.create_all()` creates the three tables `sow_projects`, `sow_resources`, and `sow_milestones` if they don't exist.

Example SQLAlchemy URL:
```text
mssql+pyodbc://USERNAME:PASSWORD@SERVER_NAME/DATABASE_NAME?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

For Windows integrated authentication:
```text
mssql+pyodbc://@SERVER_NAME/DATABASE_NAME?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes
```

If your SQL Server uses a certificate trusted by your machine, remove `TrustServerCertificate=yes` and configure certificate validation instead.

## How it works
- `GET /`: edit the SOW form with example values.
- `POST /projects`: validates/parses basic values and persists a project plus its resource and milestone rows.
- `GET /projects/<id>/print`: displays a print-optimised SOW. Select **Print / Save as PDF** and choose a printer or PDF destination.
- `GET /health`: simple health endpoint.

## Database design
- `sow_projects`: project identity, dates, region, lead, cost, scope, risk and declaration text.
- `sow_resources`: one row per assigned resource, linked to `sow_projects.id`.
- `sow_milestones`: one row per milestone/activity, linked to `sow_projects.id`.

The app uses `db.create_all()` for a starter/demo. For production, add Flask-Migrate/Alembic migrations, authentication and authorization, CSRF protection, stronger server-side validation, audit history, logging, and a secrets manager. Do not put real client or employee data into an unauthenticated deployment.

## Notes
- Reference screenshots contain personal/business details; this app is prefilled with sample values transcribed from those screenshots. Review and replace the sample data before external use.
- `end_date` is left blank at the project level because the reference showed "Not Applicable"; resource and milestone dates use the visible reference values.
\n\n## Sample SQLite database\nThe project includes `instance/sow_demo.db` with demo project `DEMO-1001`, three resources and four milestones. Run `python seed_demo.py` to add this demo record to whichever database is configured by `DATABASE_URL`. The script skips insertion if `DEMO-1001` already exists.\n