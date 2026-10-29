# Sundry Reimbursement Flask App

## Features
- Flask + SQLAlchemy; SQLite demo database created automatically.
- Separate HTML templates in `templates/`, CSS in `static/css/style.css`, and JavaScript in `static/js/form.js`.
- Add/remove expense rows, live bill/claim totals, and dependent GCC expense code field.
- Upload multiple PDFs and images to a single expense row; output is merged into one PDF per row.
- History with View, Edit and Delete.

## Run on Windows
```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Configure GCC mapping
Update `GCC_DESCRIPTION_CODES` in `app.py` with approved company values. The server validates the mapping and does not trust the submitted code.

## Database and files
The demo SQLite database is `reimbursement_demo.db`. Uploaded source files and merged PDFs are stored in `reimbursement_files/<FormNo>/`. Set `DATABASE_URL`, `REIMBURSEMENT_UPLOAD_FOLDER`, and `FLASK_SECRET_KEY` as environment variables for deployment. This is a starter application; add authentication, CSRF protection, and production database configuration before deploying.


Each expense row uses one combined attachment picker. Select multiple PDF and image files together; the application converts images and merges all selected files into one PDF for that row.
