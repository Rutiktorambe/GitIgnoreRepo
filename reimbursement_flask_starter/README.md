# Sundry Reimbursement Flask Application

## Included features
- New reimbursement form and reimbursement history.
- History search by form number, employee name or employee ID.
- Status filter and date/amount sorting.
- View, edit and delete actions (delete has a confirmation page).
- Multiple expense rows with dependent GCC expense code.
- One attachment picker per expense row; select PDFs and images together.
- PDF/image attachments are merged into one PDF per expense row.
- SQLite is the default database; configure `DATABASE_URL` for another SQLAlchemy-supported database.

## Setup (Windows)
```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python app.py
```
Open http://127.0.0.1:5000

## Important
- GCC description/code mappings in `GCC_DESCRIPTION_CODES` in `app.py` are demonstration values.
- The current ExpenseSundry schema has one general `Status` field. Separate Manager, HR, Signatory and Admin approval filters need real approval fields/tables and an approval workflow; they are not fabricated by this project.
- Back up your database and `reimbursement_files` folder before replacing an existing deployment.
