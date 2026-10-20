import os
import json
import re
import io
import uuid
import html
from types import SimpleNamespace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import bleach
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-development-secret")

# Configure SQL Server with DATABASE_URL in .env. Example is in .env.example.
# Use the configured SQL database. If no DATABASE_URL is supplied, use an empty local SQLite database.
# No sample SOWs, resources, or milestones are inserted automatically.
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///sow.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class SowProject(db.Model):
    __tablename__ = "sow_projects"

    id = db.Column(db.Integer, primary_key=True)
    project_code = db.Column(db.String(30), nullable=False, index=True)
    project_name = db.Column(db.String(100), nullable=False)
    project_team = db.Column(db.String(100))
    project_type = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    fte_count = db.Column(db.Numeric(8, 2))
    region = db.Column(db.String(100))
    client_name = db.Column(db.String(150))
    business_lead = db.Column(db.String(150))
    business_lead_designation = db.Column(db.String(150))
    business_lead_email = db.Column(db.String(255))
    billing_model = db.Column(db.String(100))
    change_effective_date = db.Column(db.Date)

    already_agreed_fte = db.Column(db.String(10))
    project_cost_inr = db.Column(db.Numeric(14, 2))
    billing_currency = db.Column(db.String(10))
    fx_rate = db.Column(db.Numeric(12, 4))
    project_cost_fx = db.Column(db.Numeric(14, 2))
    travel_cost_inr = db.Column(db.Numeric(14, 2))
    travel_currency = db.Column(db.String(10))
    travel_fx_rate = db.Column(db.Numeric(12, 4))
    travel_cost_fx = db.Column(db.Numeric(14, 2))

    executive_summary = db.Column(db.Text)
    background = db.Column(db.Text)
    in_scope = db.Column(db.Text)
    out_of_scope = db.Column(db.Text)
    dependencies_risks = db.Column(db.Text)
    required_skills = db.Column(db.Text)
    software_required = db.Column(db.Text)
    other_notes = db.Column(db.Text)
    declarations = db.Column(db.Text)
    sow_version = db.Column(db.String(30), nullable=False, default="1.0")
    change_summary = db.Column(db.Text)
    milestones_json = db.Column(db.Text, nullable=False, default="[]")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    resources = db.relationship(
        "SowResource", backref="project", cascade="all, delete-orphan",
        order_by="SowResource.sort_order"
    )

    @property
    def milestones(self):
        """Read milestones stored as JSON in sow_projects."""
        try:
            rows = json.loads(self.milestones_json or "[]")
        except (TypeError, ValueError):
            rows = []
        return [SimpleNamespace(**row) for row in rows]


class SowResource(db.Model):
    __tablename__ = "sow_resources"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("sow_projects.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    billing_level = db.Column(db.String(100))
    team = db.Column(db.String(100))
    allocation_percent = db.Column(db.Numeric(6, 2), default=100)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    responsibilities = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)


EMPTY_DATA = {
    "project_code": "",
    "project_name": "",
    "project_team": "",
    "project_type": "",
    "start_date": "",
    "end_date": "",
    "fte_count": "",
    "region": "",
    "client_name": "",
    "business_lead": "",
    "business_lead_designation": "",
    "business_lead_email": "",
    "billing_model": "",
    "change_effective_date": "",
    "already_agreed_fte": "",
    "project_cost_inr": "",
    "billing_currency": "",
    "fx_rate": "",
    "project_cost_fx": "",
    "travel_cost_inr": "",
    "travel_currency": "",
    "travel_fx_rate": "",
    "travel_cost_fx": "",
    "executive_summary": "",
    "background": "",
    "in_scope": "",
    "out_of_scope": "",
    "dependencies_risks": "",
    "required_skills": "",
    "software_required": "",
    "other_notes": "",
    "declarations": "",
}

# ============================================================
# HELPERS: INPUT CONVERSION AND FORM DATA
# ============================================================
def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def parse_decimal(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None



def database_choices(model, column_name):
    """Return distinct non-empty values already stored in the configured SQL database."""
    column = getattr(model, column_name)
    rows = (db.session.query(column)
            .filter(column.isnot(None), column != "")
            .distinct()
            .order_by(column)
            .all())
    return [row[0] for row in rows if row[0] is not None and str(row[0]).strip()]


def form_context(data=None, resources=None, milestones=None, edit_project_id="", editing_project=None):
    return {
        "data": data if data is not None else EMPTY_DATA.copy(),
        "resources": resources if resources is not None else [],
        "milestones": milestones if milestones is not None else [],
        "edit_project_id": edit_project_id,
        "editing_project": editing_project,
        "billing_levels": database_choices(SowResource, "billing_level"),
        "resource_teams": database_choices(SowResource, "team"),
        "agreed_fte_choices": database_choices(SowProject, "already_agreed_fte"),
    }


RICH_TEXT_FIELDS = {
    "executive_summary", "background", "in_scope", "out_of_scope",
    "dependencies_risks", "required_skills", "software_required",
    "other_notes", "declarations"
}
RICH_TEXT_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s", "strike",
    "ol", "ul", "li", "h2", "h3", "blockquote", "span", "a"
]
RICH_TEXT_ATTRIBUTES = {"a": ["href", "title", "target", "rel"], "span": ["style"]}
RICH_TEXT_PROTOCOLS = ["http", "https", "mailto"]


def clean_rich_text(value):
    # Keep basic formatting while removing scripts, event handlers and unsafe links.
    cleaned = bleach.clean(
        value or "",
        tags=RICH_TEXT_TAGS,
        attributes=RICH_TEXT_ATTRIBUTES,
        protocols=RICH_TEXT_PROTOCOLS,
        strip=True
    )
    return bleach.linkifier.Linker().linkify(cleaned) if False else cleaned




# ============================================================
# ROUTES: NEW SOW AND SAVED SOW PAGES
# ============================================================
@app.route("/")
def index():
    return render_template("form.html", **form_context())


@app.route("/sows")
def list_projects():
    projects = SowProject.query.order_by(SowProject.created_at.desc(), SowProject.id.desc()).all()
    return render_template("sows.html", projects=projects)


@app.route("/projects/<int:project_id>/edit")
def edit_project(project_id):
    saved = db.get_or_404(SowProject, project_id)
    data = {}
    for key in EMPTY_DATA:
        value = getattr(saved, key, None)
        if isinstance(value, (date, datetime)):
            value = value.strftime("%Y-%m-%d")
        data[key] = "" if value is None else str(value)
    resources = [(r.name, r.billing_level or "", str(r.allocation_percent if r.allocation_percent is not None else 100),
                  r.start_date.strftime("%Y-%m-%d") if r.start_date else "",
                  r.end_date.strftime("%Y-%m-%d") if r.end_date else "", r.responsibilities or "", r.team or "")
                 for r in saved.resources]
    milestones = [
        (m.milestone, str(m.action_points if m.action_points is not None else 1),
         m.start_date or "", m.end_date or "", m.description or "")
        for m in saved.milestones
    ]
    return render_template("form.html", **form_context(
        data=data, resources=resources, milestones=milestones,
        edit_project_id=saved.id, editing_project=saved
    ))



def _preview_object(draft):
    values = {key: (items[-1] if isinstance(items, list) and items else "") for key, items in draft.items()}
    data = EMPTY_DATA.copy()
    data.update(values)

    def val(name, index, default=""):
        items = draft.get(name, [])
        return items[index] if index < len(items) else default

    resources = []
    for i, name in enumerate(draft.get("resource_name[]", [])):
        if not name.strip():
            continue
        resources.append(SimpleNamespace(
            name=name, billing_level=val("resource_level[]", i),
            team=val("resource_team[]", i),
            allocation_percent=val("resource_allocation[]", i, "100"),
            start_date=parse_date(val("resource_start[]", i)),
            end_date=parse_date(val("resource_end[]", i)),
            responsibilities=val("resource_responsibilities[]", i)
        ))
    milestones = []
    for i, name in enumerate(draft.get("milestone_name[]", [])):
        if not name.strip():
            continue
        try:
            points = int(val("milestone_points[]", i, "0") or 0)
        except ValueError:
            points = 0
        milestones.append(SimpleNamespace(
            milestone=name, action_points=points,
            start_date=parse_date(val("milestone_start[]", i)),
            end_date=parse_date(val("milestone_end[]", i)),
            description=val("milestone_description[]", i)
        ))

    return SimpleNamespace(
        id="PREVIEW", created_at=datetime.now(),
        edit_project_id=values.get("edit_project_id", ""),
        project_code=values.get("project_code", ""),
        project_name=values.get("project_name", ""),
        project_team=values.get("project_team", ""),
        project_type=values.get("project_type", ""),
        start_date=parse_date(values.get("start_date")),
        end_date=parse_date(values.get("end_date")),
        fte_count=values.get("fte_count", ""),
        region=values.get("region", ""),
        client_name=values.get("client_name", ""),
        business_lead=values.get("business_lead", ""),
        business_lead_designation=values.get("business_lead_designation", ""),
        business_lead_email=values.get("business_lead_email", ""),
        billing_model=values.get("billing_model", ""),
        change_effective_date=parse_date(values.get("change_effective_date")),
        already_agreed_fte=values.get("already_agreed_fte", ""),
        project_cost_inr=values.get("project_cost_inr", ""),
        billing_currency=values.get("billing_currency", ""),
        fx_rate=values.get("fx_rate", ""),
        project_cost_fx=values.get("project_cost_fx", ""),
        travel_cost_inr=values.get("travel_cost_inr", ""),
        travel_currency=values.get("travel_currency", ""),
        travel_fx_rate=values.get("travel_fx_rate", ""),
        travel_cost_fx=values.get("travel_cost_fx", ""),
        executive_summary=clean_rich_text(values.get("executive_summary", "")),
        background=clean_rich_text(values.get("background", "")),
        in_scope=clean_rich_text(values.get("in_scope", "")),
        out_of_scope=clean_rich_text(values.get("out_of_scope", "")),
        dependencies_risks=clean_rich_text(values.get("dependencies_risks", "")),
        required_skills=clean_rich_text(values.get("required_skills", "")),
        software_required=clean_rich_text(values.get("software_required", "")),
        other_notes=clean_rich_text(values.get("other_notes", "")),
        declarations=clean_rich_text(values.get("declarations", "")),
        sow_version=values.get("sow_version", ""),
        change_summary=clean_rich_text(values.get("change_summary", "")),
        resources=resources, milestones=milestones
    )


# ============================================================
# PDF OPERATION: BUILD THE SOW PDF
# ============================================================
def generate_project_pdf(project):
    """Generate the saved PDF from the same HTML template used by the print view.

    Chromium applies the page's actual CSS print rules, so the saved PDF stays
    visually aligned with /projects/<id>/print instead of using a separate layout.
    Requires Playwright and its Chromium browser (see README.md).
    """
    from playwright.sync_api import sync_playwright

    output_dir = os.path.join(app.instance_path, "generated_pdfs")
    os.makedirs(output_dir, exist_ok=True)
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", project.project_code or "SOW")
    filename = f"{safe_code}_{project.id}.pdf"
    output_path = os.path.join(output_dir, filename)

    # Render the exact same template as the print page. The toolbar is excluded
    # by the existing .no-print CSS under @media print.
    html_doc = render_template(
        "print.html", project=project, preview_mode=False,
        pdf_exists=False, pdf_filename=filename
    )
    base_tag = f'<base href="{html.escape(request.url_root, quote=True)}">'
    css_path = os.path.join(app.static_folder, "style.css")
    with open(css_path, "r", encoding="utf-8") as css_file:
        css_text = css_file.read()
    html_doc = re.sub(
        r'<link\s+rel="stylesheet"\s+href="[^"]+"\s*/?>',
        "<style>" + css_text + "</style>", html_doc, count=1, flags=re.I
    )
    # The print document is static; editor/toolbar JavaScript is not needed in the PDF.
    html_doc = re.sub(r'<script[^>]*src="[^"]*app\.js"[^>]*></script>', "", html_doc, flags=re.I)
    html_doc = html_doc.replace("</head>", base_tag + "</head>", 1)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html_doc, wait_until="networkidle")
        page.emulate_media(media="print")
        # Use the exact @page declaration in style.css (A4 landscape, 12mm).
        # Do not pass format or margin overrides here: those can override the
        # browser print layout and cause a portrait/spacing mismatch.
        page.evaluate("document.fonts.ready")
        page.pdf(
            path=output_path,
            print_background=True,
            prefer_css_page_size=True,
            display_header_footer=False,
            scale=1,
        )
        browser.close()

    return filename


# ============================================================
# ROUTE: PREVIEW ONLY (DOES NOT COMMIT TO DATABASE)
# ============================================================
@app.route("/preview", methods=["POST"])
def preview_project():
    # Store the potentially large form server-side; only keep a short token in the session cookie.
    draft = request.form.to_dict(flat=False)
    token = uuid.uuid4().hex
    draft_dir = os.path.join(app.instance_path, "drafts")
    os.makedirs(draft_dir, exist_ok=True)
    with open(os.path.join(draft_dir, f"{token}.json"), "w", encoding="utf-8") as draft_file:
        json.dump(draft, draft_file, ensure_ascii=False)
    session["sow_draft_token"] = token
    project = _preview_object(draft)
    return render_template("print.html", project=project, preview_mode=True)


# ============================================================
# ROUTES: FINAL SAVE (HTTP layer only)
# ============================================================
@app.route("/projects/new", methods=["POST"])
def create_new_sow():
    return save_sow_to_database(project_id=None)


@app.route("/projects/<int:project_id>/update", methods=["POST"])
def update_existing_sow(project_id):
    return save_sow_to_database(project_id=project_id)


# ============================================================
# DATABASE OPERATION: CREATE OR UPDATE THE SOW AND ITS RESOURCES
# ============================================================
def save_sow_to_database(project_id=None):
    # New and edit submissions have separate URLs but share this save implementation.
    # Nothing is added to the database until both fields pass validation.
    draft_token = session.get("sow_draft_token")
    draft = {}
    draft_path = os.path.join(app.instance_path, "drafts", f"{draft_token}.json") if draft_token else ""
    if draft_path and os.path.isfile(draft_path):
        try:
            with open(draft_path, "r", encoding="utf-8") as draft_file:
                draft = json.load(draft_file)
        except (OSError, ValueError):
            draft = {}
    if not draft or not draft_token:
        flash("Your preview has expired. Please review the SOW again before saving.", "error")
        return redirect(url_for("index"))

    values = {key: (items[-1] if isinstance(items, list) and items else "") for key, items in draft.items()}
    data = EMPTY_DATA.copy()
    data.update(values)

    confirmation_summary = request.form.get("change_summary", "").strip()
    confirmation_version = request.form.get("sow_version", "").strip()
    confirmation_code = request.form.get("project_code_confirm", "").strip()
    expected_code = (data.get("project_code") or "").strip()

    if not confirmation_summary or not confirmation_version or confirmation_code != expected_code:
        project = _preview_object(draft)
        return render_template(
            "print.html", project=project, preview_mode=True,
            confirmation_error=(
                "Enter a change summary and SOW version, and confirm the project code. "
                "No database record or PDF has been created yet."
            ),
            modal_open=True,
        ), 400

    draft_project_id = (data.get("edit_project_id") or "").strip()
    if project_id is None and draft_project_id:
        flash("This draft belongs to an existing SOW. Please use the update route.", "error")
        return redirect(url_for("edit_project", project_id=int(draft_project_id)))
    if project_id is not None and (not draft_project_id or str(project_id) != draft_project_id):
        flash("The SOW being updated does not match this draft. Please preview it again.", "error")
        return redirect(url_for("edit_project", project_id=project_id))
    edit_project_id = str(project_id) if project_id is not None else ""
    existing_project = db.get_or_404(SowProject, project_id) if project_id is not None else None
    project = existing_project or SowProject()
    project.project_code = data.get("project_code", "").strip()
    project.project_name = data.get("project_name", "").strip()
    project.project_team = data.get("project_team")
    project.project_type = data.get("project_type")
    project.start_date = parse_date(data.get("start_date"))
    project.end_date = parse_date(data.get("end_date"))
    project.fte_count = parse_decimal(data.get("fte_count"))
    project.region = data.get("region")
    project.client_name = data.get("client_name")
    project.business_lead = data.get("business_lead")
    project.business_lead_designation = data.get("business_lead_designation")
    project.business_lead_email = data.get("business_lead_email")
    project.billing_model = data.get("billing_model")
    project.change_effective_date = parse_date(data.get("change_effective_date"))
    project.already_agreed_fte = data.get("already_agreed_fte")
    project.project_cost_inr = parse_decimal(data.get("project_cost_inr"))
    project.billing_currency = data.get("billing_currency")
    project.fx_rate = parse_decimal(data.get("fx_rate"))
    project.project_cost_fx = parse_decimal(data.get("project_cost_fx"))
    project.travel_cost_inr = parse_decimal(data.get("travel_cost_inr"))
    project.travel_currency = data.get("travel_currency")
    project.travel_fx_rate = parse_decimal(data.get("travel_fx_rate"))
    project.travel_cost_fx = parse_decimal(data.get("travel_cost_fx"))
    project.executive_summary = clean_rich_text(data.get("executive_summary"))
    project.background = clean_rich_text(data.get("background"))
    project.in_scope = clean_rich_text(data.get("in_scope"))
    project.out_of_scope = clean_rich_text(data.get("out_of_scope"))
    project.dependencies_risks = clean_rich_text(data.get("dependencies_risks"))
    project.required_skills = clean_rich_text(data.get("required_skills"))
    project.software_required = clean_rich_text(data.get("software_required"))
    project.other_notes = clean_rich_text(data.get("other_notes"))
    project.declarations = clean_rich_text(data.get("declarations"))
    project.sow_version = confirmation_version
    project.change_summary = clean_rich_text(confirmation_summary)
    if existing_project is not None:
        existing_project.resources.clear()

    try:
        db.session.add(project)
        db.session.flush()

        def val(name, index, default=""):
            items = draft.get(name, [])
            return items[index] if index < len(items) else default

        for i, name in enumerate(draft.get("resource_name[]", [])):
            if not name.strip():
                continue
            project.resources.append(SowResource(
                name=name.strip(),
                billing_level=val("resource_level[]", i),
                team=val("resource_team[]", i),
                allocation_percent=parse_decimal(val("resource_allocation[]", i, "100")),
                start_date=parse_date(val("resource_start[]", i)),
                end_date=parse_date(val("resource_end[]", i)),
                responsibilities=val("resource_responsibilities[]", i),
                sort_order=i,
            ))

        # Milestones live in sow_projects.milestones_json; no third table is used.
        milestone_rows = []
        for i, name in enumerate(draft.get("milestone_name[]", [])):
            if not name.strip():
                continue
            try:
                action_points = int(val("milestone_points[]", i, "0") or 0)
            except ValueError:
                action_points = 0
            milestone_rows.append({
                "milestone": name.strip(),
                "action_points": action_points,
                "start_date": val("milestone_start[]", i),
                "end_date": val("milestone_end[]", i),
                "description": val("milestone_description[]", i),
                "sort_order": i,
            })
        project.milestones_json = json.dumps(milestone_rows, ensure_ascii=False)

        # Generate PDF before DB commit. Restore the old PDF if an update cannot commit.
        pdf_dir = os.path.join(app.instance_path, "generated_pdfs")
        os.makedirs(pdf_dir, exist_ok=True)
        previous_pdf_path = os.path.join(pdf_dir, f"{re.sub(r'[^A-Za-z0-9_-]+', '_', project.project_code or 'SOW')}_{project.id}.pdf")
        previous_pdf = None
        if existing_project is not None and os.path.isfile(previous_pdf_path):
            with open(previous_pdf_path, "rb") as previous_file:
                previous_pdf = previous_file.read()
        pdf_filename = generate_project_pdf(project)
        pdf_path = os.path.join(pdf_dir, pdf_filename)
        try:
            db.session.commit()
        except Exception:
            if previous_pdf is not None:
                with open(pdf_path, "wb") as previous_file:
                    previous_file.write(previous_pdf)
            else:
                try:
                    os.remove(pdf_path)
                except FileNotFoundError:
                    pass
            raise
        session.pop("sow_draft_token", None)
        if draft_token:
            draft_path = os.path.join(app.instance_path, "drafts", f"{draft_token}.json")
            try:
                os.remove(draft_path)
            except FileNotFoundError:
                pass
        action_word = "updated" if existing_project is not None else "created"
        flash(f"SOW {action_word} in the database. PDF generated automatically: {pdf_filename}", "success")
        return redirect(url_for("print_project", project_id=project.id, saved=1))
    except Exception as exc:
        db.session.rollback()
        app.logger.exception("Could not save SOW project or generate PDF")
        flash("Could not save the SOW or generate the PDF. Check the database and PDF dependencies. Details: " + str(exc), "error")
        return render_template("form.html", **form_context(data=data, resources=[], milestones=[],
                                                            edit_project_id=edit_project_id,
                                                            editing_project=existing_project)), 500


# ============================================================
# ROUTES: VIEW AND DOWNLOAD SAVED SOW
# ============================================================
@app.route("/projects/<int:project_id>/print")
def print_project(project_id):
    project = db.get_or_404(SowProject, project_id)
    pdf_filename = f"{re.sub(r'[^A-Za-z0-9_-]+', '_', project.project_code or 'SOW')}_{project.id}.pdf"
    pdf_path = os.path.join(app.instance_path, "generated_pdfs", pdf_filename)
    return render_template("print.html", project=project, preview_mode=False,
                           pdf_exists=os.path.exists(pdf_path), pdf_filename=pdf_filename)


@app.route("/projects/<int:project_id>/pdf")
def download_project_pdf(project_id):
    project = db.get_or_404(SowProject, project_id)
    # Re-render on download so older PDFs created by the previous layout code
    # cannot be served after a template/CSS update.
    pdf_filename = generate_project_pdf(project)
    return send_from_directory(os.path.join(app.instance_path, "generated_pdfs"),
                               pdf_filename, as_attachment=True,
                               download_name=pdf_filename)


@app.route("/health")
def health():
    return {"status": "ok"}


def ensure_schema():
    """Create the two application tables and migrate legacy milestone rows if present."""
    db.create_all()
    inspector = db.inspect(db.engine)
    tables = set(inspector.get_table_names())

    if "sow_resources" in tables:
        columns = {c["name"] for c in inspector.get_columns("sow_resources")}
        if "team" not in columns:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE sow_resources ADD COLUMN team VARCHAR(100) NULL"))

    if "sow_projects" in tables:
        columns = {c["name"] for c in inspector.get_columns("sow_projects")}
        for name, sql_type in [
            ("sow_version", "VARCHAR(30) NOT NULL DEFAULT '1.0'"),
            ("change_summary", "TEXT NULL"),
            ("milestones_json", "TEXT NULL"),
        ]:
            if name not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE sow_projects ADD COLUMN {name} {sql_type}"))

    # Migrate old milestone rows to JSON before dropping the legacy third table.
    if "sow_milestones" in set(db.inspect(db.engine).get_table_names()):
        with db.engine.begin() as conn:
            projects = conn.execute(text("SELECT id, milestones_json FROM sow_projects")).mappings().all()
            for project_row in projects:
                current = project_row["milestones_json"]
                if current and current not in ("", "[]"):
                    continue
                old_rows = conn.execute(text(
                    "SELECT milestone, action_points, start_date, end_date, description, sort_order "
                    "FROM sow_milestones WHERE project_id = :pid ORDER BY sort_order, id"
                ), {"pid": project_row["id"]}).mappings().all()
                rows = [{
                    "milestone": row["milestone"] or "",
                    "action_points": row["action_points"] if row["action_points"] is not None else 1,
                    "start_date": str(row["start_date"] or "")[:10],
                    "end_date": str(row["end_date"] or "")[:10],
                    "description": row["description"] or "",
                    "sort_order": row["sort_order"] if row["sort_order"] is not None else 0,
                } for row in old_rows]
                if rows:
                    conn.execute(text(
                        "UPDATE sow_projects SET milestones_json = :data WHERE id = :pid"
                    ), {"data": json.dumps(rows, ensure_ascii=False), "pid": project_row["id"]})
            conn.execute(text("DROP TABLE sow_milestones"))


@app.before_request
def initialize_database_schema():
    # Keeps the two-table schema current and migrates legacy milestone rows once.
    ensure_schema()


if __name__ == "__main__":
    with app.app_context():
        ensure_schema()
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
