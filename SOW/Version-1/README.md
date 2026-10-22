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
- Milestones are stored as JSON in `sow_projects.milestones_json`.
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


## Separate create and update endpoints

- New SOW confirmation posts to `POST /projects/new`.
- Existing SOW confirmation posts to `POST /projects/<project_id>/update`.
- Both routes call one shared save implementation so PDF generation, validation, and transaction handling stay consistent without duplicating the save logic.


## Database design: exactly two application tables

- `sow_projects` (`SowProject`): project details, billing, SOW text, version, change summary, and milestones stored in `milestones_json`.
- `sow_resources` (`SowResource`): resource rows linked to a project through `project_id`.
- The application no longer defines a `SowMilestone` model.
- If an older database has `sow_milestones`, the startup migration copies its data into `sow_projects.milestones_json` and drops that legacy table. Back up the database before first launch after this update.

## How to find the real database code in `app.py`

- **ROUTES: NEW SOW AND SAVED SOW PAGES**: browser/page endpoints.
- **ROUTE: PREVIEW ONLY**: saves a temporary draft file only; it does not commit a project to SQL.
- **ROUTES: FINAL SAVE**: `create_new_sow()` and `update_existing_sow()` are separate HTTP routes.
- **DATABASE OPERATION**: `save_sow_to_database()` is the function that inserts/updates `SowProject` and synchronizes `SowResource` rows.
- **PDF OPERATION**: `generate_project_pdf()` creates the PDF file.
- **DATABASE SCHEMA**: `ensure_schema()` creates the two model tables and migrates old milestone rows.


## SOW version history and resource status

- Creating a new SOW assigns version `V1` and `active_flag = 'Y'`.
- Updating an active SOW inserts a **new `sow_projects` row**; it does not overwrite the prior SOW row. Versions increment automatically (`V1` → `V1.1` → `V1.2`).
- The prior project version is retained with `active_flag = 'N'`; the new version is active (`Y`). Only active versions can be edited.
- `sow_resources` includes `employee_id` (EMP ID) and `active_flag`. Each version gets a fresh resource snapshot. On revision, resource rows belonging to the previous version are retained but marked `N`; resources submitted in the new version are inserted as `Y`. If an EMP ID is removed from the new resource plan, it will have no active resource row in the new version, and its previous row remains inactive for history.
- `sow_projects` and `sow_resources` remain the only two application tables. Milestones are stored as JSON on `sow_projects`.
- The schema initializer adds the new columns to an existing database. Back up an existing database before first startup after this update.

The EMP ID is required for every resource row so resource changes can be tracked consistently by employee identifier.
