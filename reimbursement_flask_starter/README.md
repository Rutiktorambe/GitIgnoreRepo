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


## Approval status initialization (updated)
The app includes ManagerApproval, HRApproval, SignatoryApproval,
TeamHeadApproval and AdminApproval. Each defaults to `Pending` for new
expense rows. On startup and when saving edited forms, NULL/blank approval
values are set to `Pending`; existing nonblank decisions such as Approved
or Rejected are preserved.

For older databases, the app attempts to add missing approval-related columns
before normalizing values. Approval-by, approval-date and form-review comment
fields are included. Back up your database before deploying this update.

The History page filters by all five approval stages plus Form/Payment Status,
and retains Date and Amount sorting, search, clear filters, View/Edit/Delete.


## Excel serial date storage and approval defaults
FormDate, ExpenseDate, and the five approval date columns use Float storage
for Excel serial numbers. HTML date inputs are converted to serial numbers
when saved. History and view pages display readable dates; edit forms convert
serials back to YYYY-MM-DD.

New expense rows initialize Manager, HR, Signatory, Team Head and Admin
approval statuses to Pending. During edits, existing nonblank approval
decisions are preserved. Missing/blank approval values are normalized to
Pending on startup.


## Admin Approval page
Open `/admin/approval` from the Admin Approval navigation link. Search supports
form number, employee name and employee ID. Filters cover Admin, Manager, HR,
Team Head and Signatory approval statuses.

Approve updates AdminApproval, AdminApprovalBy and AdminApprovalDate for every
expense row in the form. Reject requires a nonblank reason and stores it in
FormReviewComments for every row, and sets the form Status to Rejected. The
admin name defaults to `Admin`. Add your application's login/admin-role
authorization before production use; this starter does not implement access
control.
