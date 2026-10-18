# SOW Project Workspace (Flask + SQLAlchemy)

Flask-based SOW editor with project details, cost/billing, resource planning, milestones, rich-text sections, a print-ready preview, required confirmation summary, automatic PDF generation, and edit/update support. The configured SQL database is the source of truth; no sample SOW data is inserted.

## Requirements
- Python 3.10+
- SQL Server with Microsoft ODBC Driver 18 for SQL Server, or SQLite for local development

## Run locally with an empty SQLite database
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. If `DATABASE_URL` is not set, the app uses an empty SQLite database at `instance/sow.db`. No SOWs, resources, or milestones are seeded.

## Connect to SQL Server
1. Install Microsoft ODBC Driver 18 for SQL Server.
2. Copy `.env.example` to `.env`.
3. Set `DATABASE_URL` to your SQL Server connection string, URL-encoding special characters in credentials.
4. Ensure the target database exists and the login has permission to create/alter the application's tables.
5. Run `python app.py`.

Example SQLAlchemy URL:
```text
mssql+pyodbc://USERNAME:PASSWORD@SERVER_NAME/DATABASE_NAME?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

## Database behaviour
- `sow_projects` stores project details, commercial values, scope, risk, version, and change summary.
- `sow_resources` stores resources related to a project.
- `sow_milestones` stores project milestones and activities.
- New SOW forms start blank. Existing SOWs and their child rows are loaded from the configured database.
- Billing-level, resource-team, and agreed-FTE dropdown options are derived from distinct values already stored in the database. If no values exist, those dropdowns remain blank until real records are saved.
- `/sows` lists saved SOWs. Choose Edit to update the existing database record and synchronize its resource and milestone rows.
- After preview, the confirmation popup requires an SOW version and change summary. The app generates the PDF before committing the database transaction.
- The app creates missing application tables and applies compatibility columns; it does not insert demo data. Back up an existing database before applying schema changes.

## Rich text and PDF
Narrative fields use Quill rich-text editing. HTML is sanitized server-side before storage. The final submission generates a PDF in `instance/generated_pdfs/`; the saved SOW page provides a download link.

## Production considerations
Add authentication/authorization, CSRF protection, database migrations, stronger validation, and audit logging before deploying with real client or employee data.


## Rich-text editor dependencies

- The SOW narrative editor uses a lightweight browser-native `contenteditable` editor and toolbar.
- No Quill CDN stylesheet or JavaScript is loaded, and the editor does not require an external network connection.
- Formatting controls include bold, italic, underline, headings, ordered/bulleted lists, block quotes, and clear formatting.


## Fixed form dropdowns

- Project team: Analytics, Capital, Cio-uk, Canada CIO, Finance.
- Already part of agreed FTE arrangement: Yes, No.
- Billing currency and travel currency: INR, USD, GBP, EURO.
- Billing model: FIXED - FTE, Man Days.
- New SOW FTE count defaults to 0.
- Resource allocation is entered as a percentage (100 means 100%). If your database stores allocation as a ratio (1.0 means 100%), conversion must be applied consistently in form handling and PDF display.


## Automatic FTE calculation

- The No. of FTEs field is read-only and recalculates when a resource is added, removed, or its Allocation % changes.
- Total FTE = sum of resource allocation percentages / 100.
- Examples: one 100% resource = 1.00 FTE; one 50% resource = 0.50 FTE; two 50% resources = 1.00 FTE.
- The server recalculates the total from submitted allocation values when saving, so it does not trust a client-side FTE value.
