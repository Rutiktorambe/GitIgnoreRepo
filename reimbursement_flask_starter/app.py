from reportlab.lib.enums import TA_LEFT, TA_RIGHT
import html
import os
import uuid
from datetime import date, datetime, timedelta
from xml.sax.saxutils import escape
from pathlib import Path
from io import BytesIO

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for
from flask_sqlalchemy import SQLAlchemy
from PIL import Image, ImageOps
from pypdf import PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = Path(os.environ.get("REIMBURSEMENT_UPLOAD_FOLDER", BASE_DIR / "reimbursement_files"))
DB_PATH = BASE_DIR / "reimbursement_demo.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_FILE_BYTES = 15 * 1024 * 1024

# Fixed demo mapping. Replace these values with your approved GCC descriptions/codes.
GCC_DESCRIPTION_CODES = {
    "Meals": "MEAL-002",
    "Travel": "TRV-001",
    "Accommodation": "ACC-003",
    "Office Supplies": "OFF-005",
    "Taxi / Local Transport": "TRN-004",
    "Other": "OTH-999",
}

# One database row per expense entry; FormNo + Item is the composite primary key.
class ExpenseSundry(db.Model):
    __tablename__ = "ExpenseSundry"
    FormNo = db.Column(db.String(255), primary_key=True)
    Item = db.Column(db.Integer, primary_key=True)
    FormDate = db.Column(db.Float)
    EmpID = db.Column(db.String(255))
    EName = db.Column(db.String(255))
    Manager = db.Column(db.String(255))
    TeamName = db.Column(db.String(255), nullable=True)
    Description = db.Column(db.String(255))
    GCCExpCode = db.Column(db.String(255))
    ExpenseDate = db.Column(db.Float)
    BillNo = db.Column(db.String(255))
    BillAmount = db.Column(db.Float, default=0)
    ClaimAmount = db.Column(db.Float, default=0)
    Chargeable = db.Column(db.String(20), default="NO")
    ClientName = db.Column(db.String(255))
    Comments = db.Column(db.String(1000))
    Status = db.Column(db.String(100), default="Submitted")
    DocumentID = db.Column(db.String(1000))
    FormPDFPath = db.Column(db.String(1000), nullable=True)
    AttachmentCheck = db.Column(db.String(50))
    ManagerApproval = db.Column(db.String(50), nullable=True, default="Pending", server_default=db.text("'Pending'"))
    HRApproval = db.Column(db.String(50), nullable=True, default="Pending", server_default=db.text("'Pending'"))
    SignatoryApproval = db.Column(db.String(50), nullable=True, default="Pending", server_default=db.text("'Pending'"))
    TeamHeadApproval = db.Column(db.String(50), nullable=True, default="Pending", server_default=db.text("'Pending'"))
    AdminApproval = db.Column(db.String(50), nullable=True, default="Pending", server_default=db.text("'Pending'"))
    ManagerApprovalBy = db.Column(db.String(255), nullable=True)
    HRApprovalBy = db.Column(db.String(255), nullable=True)
    SignatoryApprovalBy = db.Column(db.String(255), nullable=True)
    TeamHeadApprovalBy = db.Column(db.String(255), nullable=True)
    AdminApprovalBy = db.Column(db.String(255), nullable=True)
    FormReviewComments = db.Column(db.String(1000), nullable=True)
    ManagerApprovalDate = db.Column(db.Float, nullable=True)
    HRApprovalDate = db.Column(db.Float, nullable=True)
    SignatoryApprovalDate = db.Column(db.Float, nullable=True)
    TeamHeadApprovalDate = db.Column(db.Float, nullable=True)
    AdminApprovalDate = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f"<ExpenseSundry {self.FormNo} item={self.Item}>"


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


EXCEL_EPOCH = datetime(1899, 12, 30)


def date_to_excel_serial(value):
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text_value = str(value).strip()
    try:
        parsed = datetime.strptime(text_value[:10], "%Y-%m-%d")
        return (parsed - EXCEL_EPOCH).total_seconds() / 86400
    except ValueError:
        try:
            return float(text_value)
        except ValueError:
            raise ValueError(f"Invalid date value: {value}")


def excel_serial_to_datetime(value):
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value
    text_value = str(value).strip()
    try:
        return EXCEL_EPOCH + timedelta(days=float(text_value))
    except (ValueError, TypeError, OverflowError):
        try:
            return datetime.strptime(text_value[:10], "%Y-%m-%d")
        except ValueError:
            return None


def excel_serial_to_display(value):
    parsed = excel_serial_to_datetime(value)
    return parsed.strftime("%d-%b-%Y") if parsed else ""


def excel_serial_to_input(value):
    parsed = excel_serial_to_datetime(value)
    return parsed.strftime("%Y-%m-%d") if parsed else ""


@app.template_filter("excel_date")
def excel_date_filter(value):
    return excel_serial_to_display(value)


@app.template_filter("excel_date_input")
def excel_date_input_filter(value):
    return excel_serial_to_input(value)


def safe_remove(path, recursive=False):
    path = Path(path)
    try:
        if recursive:
            import shutil
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            path.unlink(missing_ok=True)
    except OSError:
        pass


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def merge_attachments(source_paths, output_path):
    """Merge PDFs and convert image attachments to PDF in the selected upload order."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    temporary_pdfs = []
    try:
        for source in source_paths:
            source = Path(source)
            ext = source.suffix.lower()
            if ext == ".pdf":
                writer.append(str(source))
            elif ext in {".png", ".jpg", ".jpeg"}:
                with Image.open(source) as original:
                    image = ImageOps.exif_transpose(original)
                    if image.mode != "RGB":
                        image = image.convert("RGB")
                    temp_pdf = source.with_name(source.stem + "_converted.pdf")
                    image.save(temp_pdf, "PDF", resolution=150.0)
                    temporary_pdfs.append(temp_pdf)
                    writer.append(str(temp_pdf))
            else:
                raise ValueError(f"Unsupported attachment type: {source.name}")
        with output_path.open("wb") as output:
            writer.write(output)
    finally:
        writer.close()
        for temp in temporary_pdfs:
            safe_remove(temp)


def all_rows(form_no):
    return ExpenseSundry.query.filter_by(FormNo=form_no).order_by(ExpenseSundry.Item.asc()).all()


def new_form_number():
    return "SR" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4].upper()


def seed_dummy_data():
    """Add a couple of example forms only when the database is empty."""
    if ExpenseSundry.query.first():
        return
    today = date_to_excel_serial(date.today().isoformat())
    demo = [
        ExpenseSundry(FormNo="SR-DEMO-1001", Item=1, FormDate=today, EmpID="A0566",
                      EName="Rutik Torambe", Manager="Shivam Khurana", Description="Travel",
                      GCCExpCode="TRV-001", ExpenseDate=today, BillNo="BILL-100",
                      BillAmount=1500, ClaimAmount=1500, Chargeable="NO",
                      ClientName="Client A", Comments="Taxi to client office", Status="Submitted"),
        ExpenseSundry(FormNo="SR-DEMO-1001", Item=2, FormDate=today, EmpID="A0566",
                      EName="Rutik Torambe", Manager="Shivam Khurana", Description="Meals",
                      GCCExpCode="MEAL-002", ExpenseDate=today, BillNo="BILL-101",
                      BillAmount=650, ClaimAmount=600, Chargeable="YES",
                      ClientName="Client A", Comments="Meal receipt", Status="Submitted"),
        ExpenseSundry(FormNo="SR-DEMO-1002", Item=1, FormDate=today, EmpID="A0566",
                      EName="Rutik Torambe", Manager="Shivam Khurana", Description="Office Supplies",
                      GCCExpCode="OFF-005", ExpenseDate=today, BillNo="BILL-205",
                      BillAmount=420, ClaimAmount=420, Chargeable="NO",
                      ClientName="Internal", Comments="Stationery", Status="Approved"),
    ]
    db.session.add_all(demo)
    db.session.commit()


APPROVAL_COLUMNS = {
    "TeamName": "VARCHAR(255)",
    "ManagerApproval": "VARCHAR(50)",
    "HRApproval": "VARCHAR(50)",
    "SignatoryApproval": "VARCHAR(50)",
    "TeamHeadApproval": "VARCHAR(50)",
    "AdminApproval": "VARCHAR(50)",
    "ManagerApprovalBy": "VARCHAR(255)",
    "HRApprovalBy": "VARCHAR(255)",
    "SignatoryApprovalBy": "VARCHAR(255)",
    "TeamHeadApprovalBy": "VARCHAR(255)",
    "AdminApprovalBy": "VARCHAR(255)",
    "FormReviewComments": "VARCHAR(1000)",
    "ManagerApprovalDate": "VARCHAR(30)",
    "HRApprovalDate": "VARCHAR(30)",
    "SignatoryApprovalDate": "VARCHAR(30)",
    "TeamHeadApprovalDate": "VARCHAR(30)",
    "AdminApprovalDate": "VARCHAR(30)",
}


def ensure_approval_schema():
    """Add approval and finance PDF columns if this is an older database."""
    inspector = db.inspect(db.engine)
    if not inspector.has_table("ExpenseSundry"):
        return
    existing_columns = {column["name"].lower() for column in inspector.get_columns("ExpenseSundry")}
    schema_columns = {**APPROVAL_COLUMNS, "FormPDFPath": "VARCHAR(1000)"}
    with db.engine.begin() as connection:
        for column_name, sql_type in schema_columns.items():
            if column_name.lower() not in existing_columns:
                connection.exec_driver_sql(
                    f'ALTER TABLE ExpenseSundry ADD {column_name} {sql_type} NULL'
                )


def initialize_approval_status(row):
    """Fill missing statuses only; preserve existing approval decisions."""
    for field in (
        "ManagerApproval", "HRApproval", "SignatoryApproval",
        "TeamHeadApproval", "AdminApproval"
    ):
        current_value = getattr(row, field, None)
        if current_value is None or not str(current_value).strip():
            setattr(row, field, "Pending")


def normalize_existing_approval_statuses():
    """Repair existing NULL/blank values without overwriting decisions."""
    for row in ExpenseSundry.query.all():
        initialize_approval_status(row)
    db.session.commit()


with app.app_context():
    db.create_all()
    ensure_approval_schema()
    normalize_existing_approval_statuses()
    seed_dummy_data()


def page(title, template, **context):
    return render_template(template, title=title, **context)


@app.route("/")
def home():
    return page("Overview | Sundry Reimbursement", "home.html")


@app.route("/reimbursement/new", methods=["GET", "POST"])
def new_form():
    if request.method == "POST":
        form_no = (request.form.get("FormNo") or "").strip() or new_form_number()
        try:
            save_submitted_form(form_no, is_new=True)
            flash(f"Form {form_no} saved successfully.", "success")
            return redirect(url_for("history"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Could not save form: {exc}", "error")
            return redirect(url_for("new_form"))
    return page("New Form | Reimbursement", "form.html", mode="new", form_no=new_form_number(),
                rows=[blank_row(1)], header={}, today=date.today().isoformat(),
                descriptions=descriptions(), clients=clients(), gcc_codes=GCC_DESCRIPTION_CODES)


@app.route("/reimbursement/history")
def history():
    """Load saved reimbursement forms and prepare data for the history screen.

    Optional URL filters: ?q=<form/name/employee-id>, ?status=Approved,
    and ?sort=amount. The page also supports live client-side filtering.
    """
    all_rows_summary = all_forms_summary()
    search_text = (request.args.get("q") or "").strip().lower()
    selected_status = (request.args.get("status") or "").strip().lower()
    sort_by = (request.args.get("sort") or "date").strip().lower()

    # Build filter choices from real statuses stored in ExpenseSundry.
    statuses = sorted({
        str(item.get("status") or "Submitted")
        for item in all_rows_summary
        if str(item.get("status") or "Submitted").strip()
    })

    rows = all_rows_summary
    if search_text:
        rows = [
            item for item in rows
            if search_text in str(item.get("form_no") or "").lower()
            or search_text in str(item.get("name") or "").lower()
            or search_text in str(item.get("emp_id") or "").lower()
        ]

    if selected_status:
        rows = [
            item for item in rows
            if selected_status == str(item.get("status") or "Submitted").lower()
        ]

    if sort_by == "amount":
        rows.sort(
            key=lambda item: (item.get("total") or 0, item.get("form_no") or ""),
            reverse=True,
        )
    else:
        rows.sort(
            key=lambda item: (item.get("form_date") or "", item.get("form_no") or ""),
            reverse=True,
        )

    return page(
        "Reimbursement History",
        "history.html",
        forms=rows,
        statuses=statuses,
        selected_status=selected_status,
        search_text=search_text,
        sort_by=sort_by,
        total_forms=len(rows),
    )


@app.route("/reimbursement/<form_no>/<action>", methods=["GET", "POST"])
def form_action(form_no, action):
    if action not in {"view", "edit", "delete"}:
        abort(404)
    rows = all_rows(form_no)
    if not rows:
        abort(404)
    if action == "delete":
        if request.method == "POST":
            safe_remove(UPLOAD_ROOT / form_no, recursive=True)
            for row in rows:
                db.session.delete(row)
            db.session.commit()
            flash(f"Form {form_no} deleted.", "success")
            return redirect(url_for("history"))
        return page("Delete Form", "delete.html", form_no=form_no)
    if action == "view":
        return page("View Form", "view.html", form_no=form_no, rows=rows)
    if request.method == "POST":
        try:
            save_submitted_form(form_no, is_new=False)
            flash(f"Form {form_no} updated.", "success")
            return redirect(url_for("form_action", form_no=form_no, action="view"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Could not update form: {exc}", "error")
            return redirect(url_for("form_action", form_no=form_no, action="edit"))
    first = rows[0]
    header = {"EName": first.EName or "", "EmpID": first.EmpID or "",
              "Manager": first.Manager or "", "TeamName": getattr(first, "TeamName", "") or "", "FormDate": excel_serial_to_input(first.FormDate) or date.today().isoformat()}
    return page("Edit Form", "form.html", mode="edit", form_no=form_no, rows=rows,
                header=header, today=date.today().isoformat(),
                descriptions=descriptions(), clients=clients(), gcc_codes=GCC_DESCRIPTION_CODES)




@app.route("/admin/approval", methods=["GET", "POST"])
def admin_approval():
    if request.method == "POST":
        form_no = (request.form.get("form_no") or "").strip()
        decision = (request.form.get("decision") or "").strip().title()
        comments = (request.form.get("FormReviewComments") or "").strip()
        admin_name = (request.form.get("AdminApprovalBy") or "").strip() or "Admin"
        if decision not in {"Approved", "Rejected"}:
            flash("Choose Approve or Reject.", "error")
            return redirect(url_for("admin_approval"))
        if decision == "Rejected" and not comments:
            flash("Rejection reason is mandatory.", "error")
            return redirect(url_for("admin_approval"))
        rows = all_rows(form_no)
        if not rows:
            abort(404)
        approval_date = date_to_excel_serial(date.today().isoformat())
        for row in rows:
            row.AdminApproval = decision
            row.AdminApprovalBy = admin_name
            row.AdminApprovalDate = approval_date
            if decision == "Rejected":
                row.FormReviewComments = comments
                row.Status = "Rejected"
            else:
                required = [row.ManagerApproval, row.HRApproval, row.SignatoryApproval,
                            row.TeamHeadApproval, row.AdminApproval]
                if all((v or "").strip().lower() in {"approved", "not required"} for v in required):
                    row.Status = "Approved"
                row.FormReviewComments = comments or row.FormReviewComments
        db.session.commit()
        flash(f"Form {form_no} {decision.lower()} successfully.", "success")
        return redirect(url_for("admin_approval"))

    search_text = (request.args.get("q") or "").strip().lower()
    selected = {key: (request.args.get(key) or "").strip()
                for key in ("admin", "manager", "hr", "teamhead", "signatory")}
    grouped = {}
    for row in ExpenseSundry.query.order_by(ExpenseSundry.FormDate.desc(), ExpenseSundry.Item.asc()).all():
        item = grouped.setdefault(row.FormNo, {
            "form_no": row.FormNo, "name": row.EName or "", "emp_id": row.EmpID or "",
            "manager_name": row.Manager or "", "form_date": excel_serial_to_display(row.FormDate),
            "total": 0.0, "count": 0, "admin": row.AdminApproval or "Pending",
            "manager": row.ManagerApproval or "Pending", "hr": row.HRApproval or "Pending",
            "teamhead": row.TeamHeadApproval or "Pending", "signatory": row.SignatoryApproval or "Pending",
            "comments": row.FormReviewComments or ""
        })
        item["total"] += row.ClaimAmount or 0
        item["count"] += 1

    forms = []
    for item in grouped.values():
        text_match = not search_text or any(
            search_text in str(item[k]).lower()
            for k in ("form_no", "name", "emp_id", "manager_name")
        )
        filter_match = all(
            not selected[k] or str(item[k]).lower() == selected[k].lower()
            for k in selected
        )
        if text_match and filter_match:
            forms.append(item)
    forms.sort(key=lambda x: x["form_no"], reverse=True)
    return page("Admin Approval", "admin_approval.html", forms=forms,
                search_text=search_text, selected=selected,
                approval_options=["Pending", "Approved", "Rejected", "Not Required"])


@app.route("/finance")
def finance_dashboard():
    """Finance team workspace for generating and downloading reimbursement PDFs."""
    q = (request.args.get("q") or "").strip().lower()
    forms = finance_forms_summary()
    if q:
        forms = [f for f in forms if q in f["form_no"].lower() or q in f["name"].lower() or q in f["emp_id"].lower()]
    return page("Finance Dashboard", "finance_dashboard.html", forms=forms, search_text=q)


@app.route("/finance/<form_no>/generate-pdf", methods=["POST"])
def finance_generate_pdf(form_no):
    rows = all_rows(form_no)
    if not rows:
        abort(404)
    try:
        path = generate_record_pdf(form_no, rows)
        flash(f"PDF generated and saved for {form_no}.", "success")
        return send_file(path, as_attachment=True, download_name=f"{form_no}_form.pdf")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not generate PDF: {exc}", "error")
        return redirect(url_for("finance_dashboard"))



@app.route("/finance/<form_no>/download-full", methods=["GET"])
def finance_download_full(form_no):
    """Build the form PDF plus every available item attachment into one download."""
    rows = all_rows(form_no)
    if not rows:
        abort(404)

    writer = None
    try:
        # Reuse the saved form PDF when present; otherwise generate and save it.
        saved_path = rows[0].FormPDFPath
        form_pdf = Path(saved_path).resolve() if saved_path else None
        if not form_pdf or not form_pdf.is_file():
            form_pdf = Path(generate_record_pdf(form_no, rows)).resolve()

        # Confirm the generated form PDF is inside the configured upload directory.
        upload_root = UPLOAD_ROOT.resolve()
        try:
            form_pdf.relative_to(upload_root)
        except ValueError:
            abort(403)

        writer = PdfWriter()
        writer.append(str(form_pdf))

        # Each row's DocumentID points to the combined PDF for that expense item.
        # Add each attachment once, preserving expense item order.
        for row in rows:
            if not row.DocumentID:
                continue

            attachment_path = Path(row.DocumentID).resolve()
            try:
                attachment_path.relative_to(upload_root)
            except ValueError:
                abort(403)

            if not attachment_path.is_file():
                app.logger.warning(
                    "Attachment missing for form %s, item %s: %s",
                    form_no, row.Item, attachment_path
                )
                continue

            if attachment_path.suffix.lower() != ".pdf":
                app.logger.warning(
                    "Skipping non-PDF attachment for form %s, item %s: %s",
                    form_no, row.Item, attachment_path
                )
                continue

            writer.append(str(attachment_path))

        # Return an in-memory PDF response; avoids stale/locked output files
        # and ensures Flask streams a fresh application/pdf attachment.
        pdf_buffer = BytesIO()
        writer.write(pdf_buffer)
        writer.close()
        writer = None
        pdf_buffer.seek(0)

        safe_form_no = re.sub(r"[^A-Za-z0-9_-]+", "_", str(form_no)).strip("_") or "Reimbursement"
        response = send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{safe_form_no}_full.pdf",
            max_age=0
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    except Exception:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        db.session.rollback()
        app.logger.exception("Could not create full reimbursement PDF for %s", form_no)
        return (
            "Could not create the full reimbursement PDF. "
            "Check the Flask server log for the detailed error.",
            500,
            {"Content-Type": "text/plain; charset=utf-8"}
        )


@app.route("/reimbursement/<form_no>/attachment/<int:item>")
def download_pdf(form_no, item):
    row = db.session.get(ExpenseSundry, (form_no, item))
    if not row or not row.DocumentID:
        abort(404)
    path = Path(row.DocumentID).resolve()
    # Only permit downloads from the configured attachment root.
    root = UPLOAD_ROOT.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        abort(403)
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=f"{form_no}_{item}.pdf")



def finance_forms_summary():
    grouped = {}
    for row in ExpenseSundry.query.order_by(ExpenseSundry.FormDate.desc(), ExpenseSundry.Item.asc()).all():
        item = grouped.setdefault(row.FormNo, {
            "form_no": row.FormNo, "name": row.EName or "", "emp_id": row.EmpID or "",
            "form_date": excel_serial_to_display(row.FormDate), "status": row.Status or "Submitted",
            "count": 0, "total": 0.0, "pdf_saved": bool(row.FormPDFPath and Path(row.FormPDFPath).is_file())
        })
        item["count"] += 1
        item["total"] += row.ClaimAmount or 0
        item["pdf_saved"] = item["pdf_saved"] or bool(row.FormPDFPath and Path(row.FormPDFPath).is_file())
    return sorted(grouped.values(), key=lambda x: x["form_no"], reverse=True)






def generate_record_pdf(form_no, rows):
    """Generate a two-section reimbursement PDF: summary/approvals, then expense entries."""
    if not rows:
        raise ValueError(f"No reimbursement rows found for {form_no}")

    form_folder = UPLOAD_ROOT / form_no
    form_folder.mkdir(parents=True, exist_ok=True)
    output_path = (form_folder / f"{form_no}_form.pdf").resolve()

    generated_at = datetime.now().astimezone()
    forwarded_ip = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_ip.split(",")[0].strip() if forwarded_ip else (request.remote_addr or "Unknown")

    PURPLE = colors.HexColor("#35245e")
    LIGHT_PURPLE = colors.HexColor("#f0edf8")
    GRID = colors.HexColor("#d8d4e3")
    MUTED = colors.HexColor("#687386")
    PALE = colors.HexColor("#f7f6fa")
    WHITE = colors.white

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="RTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, textColor=PURPLE, alignment=TA_LEFT, spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name="RSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=PURPLE, spaceBefore=7, spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="RLabel", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7, leading=8.5, textColor=MUTED
    ))
    styles.add(ParagraphStyle(
        name="RValue", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=10.5, textColor=colors.HexColor("#172033")
    ))
    styles.add(ParagraphStyle(
        name="RCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=6.5, leading=8, textColor=colors.HexColor("#172033")
    ))
    styles.add(ParagraphStyle(
        name="RHead", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=6.5, leading=8, textColor=WHITE
    ))
    styles.add(ParagraphStyle(
        name="RTotal", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=13, leading=16, textColor=PURPLE, alignment=TA_RIGHT
    ))

    def fmt(value):
        if value is None or str(value).strip() == "":
            return "—"
        if isinstance(value, (date, datetime)):
            return value.strftime("%d-%b-%Y")
        return str(value)

    def display_date(value):
        if value is None or str(value).strip() == "":
            return "—"
        try:
            converted = excel_serial_to_display(value)
            return converted or fmt(value)
        except Exception:
            return fmt(value)

    def p(value, style="RCell"):
        return Paragraph(html.escape(fmt(value)).replace("\n", "<br/>"), styles[style])

    first = rows[0]
    story = []

    # Branded document header.
    logo_path = BASE_DIR / "static" / "images" / "intact_logo.png"
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=31 * mm, height=17 * mm, kind="proportional")
    else:
        logo = Paragraph("<b><font color='#C8102E'>[ intact ]</font></b>", styles["RTitle"])

    header = Table([[
        logo,
        [
            Paragraph("SUNDRY REIMBURSEMENT", styles["RLabel"]),
            Paragraph(html.escape(str(form_no)), styles["RTitle"]),
            Paragraph("Employee claim record", styles["RLabel"])
        ]
    ]], colWidths=[42 * mm, 226 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.4, PURPLE),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([header, Spacer(1, 3 * mm)])

    # SECTION 1 — employee information, approval audit and total.
    story.append(Paragraph("01 · Employee & approval summary", styles["RSection"]))

    employee_fields = [
        ("EMPLOYEE NAME", first.EName),
        ("EMPLOYEE ID", first.EmpID),
        ("LINE MANAGER", first.Manager),
        ("TEAM NAME", getattr(first, "TeamName", None)),
        ("FORM DATE", display_date(first.FormDate)),
    ]
    employee_cells = []
    for label, value in employee_fields:
        employee_cells.append([
            Paragraph(html.escape(label), styles["RLabel"]),
            Paragraph(html.escape(fmt(value)), styles["RValue"])
        ])

    employee_table = Table(
        [[*employee_cells]],
        colWidths=[53.6 * mm] * 5
    )
    employee_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([employee_table, Spacer(1, 2 * mm)])

    approval_stages = [
        ("Manager", "ManagerApproval", "ManagerApprovalBy", "ManagerApprovalDate"),
        ("HR", "HRApproval", "HRApprovalBy", "HRApprovalDate"),
        ("Signatory", "SignatoryApproval", "SignatoryApprovalBy", "SignatoryApprovalDate"),
        ("Team Head", "TeamHeadApproval", "TeamHeadApprovalBy", "TeamHeadApprovalDate"),
        ("Admin", "AdminApproval", "AdminApprovalBy", "AdminApprovalDate"),
    ]


    # Five compact approval cards. Each card shows status prominently,
    # with approver and approval date in smaller supporting text.
    approval_cards = []
    for label, status_field, by_field, date_field in approval_stages:
        status = getattr(first, status_field, None) or "Pending"
        approver = getattr(first, by_field, None) or "—"
        approved_on = display_date(getattr(first, date_field, None))

        status_color = (
            colors.HexColor("#18794e")
            if str(status).strip().lower() == "approved"
            else colors.HexColor("#b54708")
            if str(status).strip().lower() == "pending"
            else colors.HexColor("#b42318")
            if str(status).strip().lower() == "rejected"
            else PURPLE
        )

        card_content = [
            Paragraph(html.escape(label.upper()), styles["RLabel"]),
            Paragraph(
                f'<font color="{status_color.hexval()}"><b>{html.escape(str(status))}</b></font>',
                styles["RValue"]
            ),
            Paragraph(f"By: {html.escape(fmt(approver))}", styles["RLabel"]),
            Paragraph(f"On: {html.escape(fmt(approved_on))}", styles["RLabel"]),
        ]
        approval_cards.append(card_content)

    cards_table = Table(
        [approval_cards],
        colWidths=[53.6 * mm] * 5
    )
    cards_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([cards_table, Spacer(1, 2 * mm)])

    total_bill = sum(money(r.BillAmount) for r in rows)
    total_claim = sum(money(r.ClaimAmount) for r in rows)
    total_table = Table([[
        Paragraph("TOTAL CLAIM AMOUNT", styles["RLabel"]),
        Paragraph(f"{total_claim:,.2f}", styles["RTotal"])
    ]], colWidths=[190 * mm, 78 * mm])
    total_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_PURPLE),
        ("BOX", (0, 0), (-1, -1), 0.7, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([total_table, Spacer(1, 4 * mm)])

    # SECTION 2 — all expense-level fields in ONE table.
    story.append(Paragraph("02 · Expense entries", styles["RSection"]))

    entry_headers = [
        "ITEM", "EXPENSE TYPE", "GCC CODE", "EXPENSE DATE",
        "BILL NO.", "BILL AMOUNT", "CLAIM AMOUNT",
        "CHARGEABLE", "CLIENT", "COMMENTS"
    ]
    entry_data = [[p(h, "RHead") for h in entry_headers]]

    for row in rows:
        entry_data.append([
            p(row.Item),
            p(row.Description),
            p(row.GCCExpCode),
            p(display_date(row.ExpenseDate)),
            p(row.BillNo),
            p(f"{money(row.BillAmount):,.2f}"),
            p(f"{money(row.ClaimAmount):,.2f}"),
            p(row.Chargeable),
            p(row.ClientName),
            p(row.Comments)
        ])

    entry_widths = [
        10 * mm, 34 * mm, 22 * mm, 27 * mm, 25 * mm,
        27 * mm, 27 * mm, 21 * mm, 35 * mm, 40 * mm
    ]
    entry_table = Table(entry_data, colWidths=entry_widths, repeatRows=1)
    entry_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (5, 1), (6, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(entry_table)

    # Compact attachment register: one row per expense item.
    story.append(Paragraph("Attachment register", styles["RSection"]))
    attachment_data = [[
        p("ITEM NO.", "RHead"),
        p("ATTACHMENT PATH", "RHead")
    ]]
    for row in rows:
        attachment_path = getattr(row, "DocumentID", None)
        attachment_data.append([
            p(row.Item),
            p(attachment_path if attachment_path else "No attachment")
        ])

    attachment_table = Table(
        attachment_data,
        colWidths=[25 * mm, 243 * mm],
        repeatRows=1
    )
    attachment_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(attachment_table)

    # Security / document integrity notice.
    story.extend([
        Spacer(1, 3 * mm),
        Paragraph(
            "<b>SECURITY NOTICE</b><br/>"
            "This document is generated by the computer. Any modification is prohibited "
            "and firmly unauthorized modification is prohibited. In case of any issues "
            "for the PDF, please contact with finance team.",
            ParagraphStyle(
                "SecurityNotice",
                parent=styles["RLabel"],
                fontName="Helvetica",
                fontSize=7,
                leading=9,
                textColor=MUTED
            )
        )
    ])

    # Footer on every page.
    def add_page_footer(canvas, doc):
        canvas.saveState()
        page_width, _ = landscape(A4)
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 12 * mm, page_width - 14 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        timestamp = generated_at.strftime("%d-%b-%Y %I:%M:%S %p %Z")
        canvas.drawString(14 * mm, 7 * mm, f"Generated: {timestamp} | IP: {client_ip}")
        canvas.drawRightString(page_width - 14 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=10 * mm,
        bottomMargin=16 * mm,
        title=f"Sundry Reimbursement - {form_no}",
        author="Finance"
    )
    doc.build(story, onFirstPage=add_page_footer, onLaterPages=add_page_footer)

    for row in rows:
        row.FormPDFPath = str(output_path)
    db.session.commit()
    return output_path


def descriptions():
    return list(GCC_DESCRIPTION_CODES.keys())


def clients():
    return ["Select Client", "Client A", "Client B", "Client C", "Internal"]


def blank_row(item):
    return ExpenseSundry(FormNo="", Item=item, Description="Meals", BillAmount=0, ClaimAmount=0, Chargeable="NO")


def all_forms_summary():
    """
    Aggregate the saved expense rows into one history record per FormNo.
    ExpenseSundry currently has one Status column only; it does not store
    separate Manager, HR, Signatory, or Admin approval states.
    """
    grouped = {}
    for row in ExpenseSundry.query.order_by(ExpenseSundry.FormDate.desc(), ExpenseSundry.FormNo, ExpenseSundry.Item).all():
        entry = grouped.setdefault(row.FormNo, {
            "form_no": row.FormNo, "name": row.EName, "emp_id": row.EmpID,
            "form_date": excel_serial_to_input(row.FormDate), "form_date_display": excel_serial_to_display(row.FormDate), "status": row.Status, "count": 0, "total": 0.0,
            "manager_approval": row.ManagerApproval or "Pending",
            "hr_approval": row.HRApproval or "Pending",
            "signatory_approval": row.SignatoryApproval or "Pending",
            "teamhead_approval": row.TeamHeadApproval or "Pending",
            "admin_approval": row.AdminApproval or "Pending",
        })
        entry["count"] += 1
        entry["total"] += row.ClaimAmount or 0
        row_form_date = excel_serial_to_input(row.FormDate)
        if row_form_date and (not entry["form_date"] or row_form_date > entry["form_date"]):
            entry["form_date"] = row_form_date
            entry["form_date_display"] = excel_serial_to_display(row.FormDate)
    return sorted(grouped.values(), key=lambda f: (f["form_date"] or "", f["form_no"]), reverse=True)


def save_submitted_form(form_no, is_new):
    emp_id = (request.form.get("EmpID") or "").strip()
    name = (request.form.get("EName") or "").strip()
    manager = (request.form.get("Manager") or "").strip()
    form_date = date_to_excel_serial((request.form.get("FormDate") or date.today().isoformat()).strip())
    descriptions_in = request.form.getlist("Description[]")
    if not name or not emp_id:
        raise ValueError("Employee name and Employee ID are required.")
    if not descriptions_in:
        raise ValueError("Add at least one expense entry.")

    existing = {} if is_new else {r.Item: r for r in all_rows(form_no)}
    form_folder = UPLOAD_ROOT / form_no
    form_folder.mkdir(parents=True, exist_ok=True)
    fields = {
        "Item": request.form.getlist("Item[]"),
        "GCCExpCode": request.form.getlist("GCCExpCode[]"),
        "ExpenseDate": request.form.getlist("ExpenseDate[]"),
        "BillNo": request.form.getlist("BillNo[]"),
        "BillAmount": request.form.getlist("BillAmount[]"),
        "ClaimAmount": request.form.getlist("ClaimAmount[]"),
        "Chargeable": request.form.getlist("Chargeable[]"),
        "ClientName": request.form.getlist("ClientName[]"),
        "Comments": request.form.getlist("Comments[]"),
    }
    keep = set()
    staged = []
    try:
        for index, desc in enumerate(descriptions_in):
            # Reassign item numbers in visual order to keep FormNo+Item unique.
            item = index + 1
            keep.add(item)
            old_item = int(fields["Item"][index]) if index < len(fields["Item"]) and fields["Item"][index].isdigit() else item
            row = existing.get(old_item) or existing.get(item) or ExpenseSundry(FormNo=form_no, Item=item)
            row.FormNo, row.Item = form_no, item
            row.FormDate, row.EmpID, row.EName, row.Manager = form_date, emp_id, name, manager
            row.TeamName = (request.form.get("TeamName") or "").strip() or getattr(row, "TeamName", None)
            row.Description = (desc or "").strip()
            if row.Description not in GCC_DESCRIPTION_CODES:
                raise ValueError(f"Unknown expense description: {row.Description}")
            row.GCCExpCode = GCC_DESCRIPTION_CODES[row.Description]
            row.ExpenseDate = date_to_excel_serial(
                fields["ExpenseDate"][index].strip()
                if index < len(fields["ExpenseDate"]) and fields["ExpenseDate"][index]
                else None
            )
            for field in ["BillNo", "ClientName", "Comments"]:
                values = fields[field]
                setattr(row, field, values[index].strip() if index < len(values) and values[index] else "")
            row.BillAmount = money(fields["BillAmount"][index] if index < len(fields["BillAmount"]) else 0)
            row.ClaimAmount = money(fields["ClaimAmount"][index] if index < len(fields["ClaimAmount"]) else 0)
            row.Chargeable = fields["Chargeable"][index] if index < len(fields["Chargeable"]) else "NO"
            row.Status = row.Status or "Submitted"

            # Separate PDF and image pickers let users select both file types for one row.
            uploads = [f for field_name in (f"attachments_pdf_{index}", f"attachments_image_{index}", f"attachments_{index}")
                       for f in request.files.getlist(field_name) if f and f.filename]
            if uploads:
                saved_sources = []
                for upload in uploads:
                    if not allowed_file(upload.filename):
                        raise ValueError(f"Unsupported attachment type: {upload.filename}")
                    upload.stream.seek(0, os.SEEK_END)
                    size = upload.stream.tell()
                    upload.stream.seek(0)
                    if size > MAX_FILE_BYTES:
                        raise ValueError(f"{upload.filename} exceeds the 15 MB limit.")
                    filename = f"{uuid.uuid4().hex}_{Path(upload.filename).name}"
                    destination = form_folder / filename
                    upload.save(destination)
                    saved_sources.append(destination)
                    staged.append(destination)
                pdf_path = form_folder / f"{form_no}_{item}.pdf"
                merge_attachments(saved_sources, pdf_path)
                staged.append(pdf_path)
                row.DocumentID = str(pdf_path.resolve())
                row.AttachmentCheck = "Y"
            initialize_approval_status(row)
            db.session.add(row)

        for old_item, old_row in existing.items():
            if old_item not in keep:
                db.session.delete(old_row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Leave pre-existing PDFs intact; only clean staged source files, not PDFs
        # that may have replaced existing versions.
        for p in staged:
            if p.suffix.lower() != ".pdf" or "_converted" in p.stem:
                safe_remove(p)
        raise


if __name__ == "__main__":
    print("Starting reimbursement demo. Open http://127.0.0.1:5000")
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Attachment folder: {UPLOAD_ROOT}")
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
