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
    sow_version = db.Column(db.String(30), nullable=False, default="V1")
    active_flag = db.Column(db.String(1), nullable=False, default="Y", index=True)
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
    employee_id = db.Column(db.String(50), nullable=False, default="", index=True)
    name = db.Column(db.String(150), nullable=False)
    billing_level = db.Column(db.String(100))
    active_flag = db.Column(db.String(3), nullable=False, default="Y", index=True)
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
                  r.end_date.strftime("%Y-%m-%d") if r.end_date else "", r.responsibilities or "", r.team or "", r.employee_id or "")
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



def next_sow_version(current_version=None):
    """Return V1 for a new SOW and increment the minor version for each revision."""
    if not current_version:
        return "V1"
    match = re.fullmatch(r"V?(\d+)(?:\.(\d+))?", str(current_version).strip(), re.IGNORECASE)
    if not match:
        return "V1.1"
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    return f"V{major}.{minor + 1}"


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
            employee_id=val("resource_employee_id[]", i).strip(),
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

def _pdf_text(value):
    """Convert plain values safely for ReportLab."""
    if value is None or value == "":
        return "—"
    return html.escape(str(value))


def _pdf_rich(value):
    """Preserve rich-text formatting while decoding HTML entities for ReportLab."""
    if value is None or value == "":
        return "—"

    # Some saved editor values contain entities that have already been escaped.
    # Decode repeatedly so strings such as &amp;#8226; and &amp;nbsp; become
    # their actual bullet/space characters before ReportLab parses the paragraph.
    source = str(value)
    for _ in range(3):
        decoded = html.unescape(source)
        if decoded == source:
            break
        source = decoded

    source = source.replace("\xa0", " ")
    source = source.replace("\u2022", "•")
    source = re.sub(r"(?i)<(strong|b)(?:\s+[^>]*)?>", "<b>", source)
    source = re.sub(r"(?i)</(strong|b)\s*>", "</b>", source)
    source = re.sub(r"(?i)<(em|i)(?:\s+[^>]*)?>", "<i>", source)
    source = re.sub(r"(?i)</(em|i)\s*>", "</i>", source)
    source = re.sub(r"(?i)<u(?:\s+[^>]*)?>", "<u>", source)
    source = re.sub(r"(?i)</u\s*>", "</u>", source)
    source = re.sub(r"(?i)<br\s*/?>", "<br/>", source)
    source = re.sub(r"(?i)</p\s*>", "<br/><br/>", source)
    source = re.sub(r"(?i)<p(?:\s+[^>]*)?>", "", source)

    # Convert ordered/unordered list items into actual bullet/number text,
    # not HTML entity strings (ReportLab does not render all browser entities).
    list_counter = {"value": 0, "ordered": False}
    def open_list(match):
        list_counter["value"] = 0
        list_counter["ordered"] = match.group(1).lower() == "ol"
        return "<br/>"
    def close_list(_match):
        list_counter["value"] = 0
        list_counter["ordered"] = False
        return "<br/>"
    def list_item(_match):
        if list_counter["ordered"]:
            list_counter["value"] += 1
            return f"<br/>{list_counter['value']}. "
        return "<br/>• "
    source = re.sub(r"(?i)<(ul|ol)(?:\s+[^>]*)?>", open_list, source)
    source = re.sub(r"(?i)</(ul|ol)\s*>", close_list, source)
    source = re.sub(r"(?i)<li(?:\s+[^>]*)?>", list_item, source)
    source = re.sub(r"(?i)</li\s*>", "", source)
    source = re.sub(r"(?i)<(div|section)(?:\s+[^>]*)?>", "", source)
    source = re.sub(r"(?i)</(div|section)\s*>", "<br/>", source)

    # Escape text nodes only. Keep a small safe set of ReportLab formatting tags.
    parts = re.split(r"(<[^>]+>)", source)
    safe_parts = []
    for part in parts:
        if not part:
            continue
        match = re.fullmatch(r"<\s*(/?)\s*([A-Za-z]+)(?:\s+([^>]*))?\s*/?\s*>", part)
        if not match:
            safe_parts.append(part if part.startswith("<") else html.escape(part, quote=False))
            continue
        closing, tag, attrs = match.groups()
        tag = tag.lower()
        if tag == "br":
            safe_parts.append("<br/>")
        elif tag in {"b", "i", "u"}:
            safe_parts.append(f"</{tag}>" if closing else f"<{tag}>")
        elif tag == "font" and closing:
            safe_parts.append("</font>")
        elif tag == "font":
            color_match = re.search(r"(?i)color\s*=\s*['\"]?(#[0-9a-f]{6}|[a-z]+)", attrs or "")
            if color_match:
                safe_parts.append(f'<font color="{color_match.group(1)}">')

    result = "".join(safe_parts).strip()
    result = re.sub(r"(?:<br/>\\s*){3,}", "<br/><br/>", result)
    return result or "—"


def generate_project_pdf(project):
    """Generate the saved SOW PDF with ReportLab, following the preview's content order and branding."""
    from reportlab.platypus import Image

    output_dir = os.path.join(app.instance_path, "generated_pdfs")
    os.makedirs(output_dir, exist_ok=True)
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", project.project_code or "SOW")
    filename = f"{safe_code}_{project.id}.pdf"
    output_path = os.path.join(output_dir, filename)

    navy = colors.HexColor("#173B59")
    gold = colors.HexColor("#C7A76A")
    pale = colors.HexColor("#F5F3ED")
    grid = colors.HexColor("#D9DEE5")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SOWTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=20, leading=24, textColor=navy, alignment=TA_LEFT, spaceAfter=4))
    styles.add(ParagraphStyle(name="SOWSub", parent=styles["Normal"], fontSize=8.5, leading=12,
        textColor=colors.HexColor("#596575")))
    styles.add(ParagraphStyle(name="SOWSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=navy, spaceBefore=12, spaceAfter=7, keepWithNext=True))
    styles.add(ParagraphStyle(name="SOWCell", parent=styles["BodyText"], fontSize=7.5, leading=10,
        textColor=colors.HexColor("#263445"), wordWrap="CJK"))
    styles.add(ParagraphStyle(name="SOWLabel", parent=styles["BodyText"], fontSize=6.5, leading=8,
        textColor=colors.HexColor("#687386")))
    styles.add(ParagraphStyle(name="SOWRich", parent=styles["BodyText"], fontSize=8, leading=12,
        textColor=colors.HexColor("#263445"), spaceAfter=6, allowWidows=0, allowOrphans=0))
    styles.add(ParagraphStyle(name="SOWSubheading", parent=styles["Heading3"],
        fontName="Helvetica-Bold", fontSize=9.2, leading=12, textColor=navy,
        backColor=colors.HexColor("#F1F4F7"), borderColor=gold, borderWidth=0,
        borderPadding=(5, 7, 5, 7), spaceBefore=5, spaceAfter=5, keepWithNext=True))
    styles.add(ParagraphStyle(name="SOWTableHeader", parent=styles["BodyText"],
        fontName="Helvetica-Bold", fontSize=7.5, leading=9,
        textColor=colors.white, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="SOWFooter", parent=styles["BodyText"], fontSize=7, leading=9,
        textColor=colors.HexColor("#6B7280")))

    def para(value, style="SOWCell", rich=False):
        markup = _pdf_rich(value) if rich else _pdf_text(value)
        return Paragraph(markup, styles[style])

    page_width = landscape(A4)[0]
    usable_width = page_width - 30 * mm

    def section(title):
        return Paragraph(title, styles["SOWSection"])

    def info_grid(items, cols=3):
        col_width = usable_width / cols
        rows = []
        for offset in range(0, len(items), cols):
            row = []
            for label, value in items[offset:offset + cols]:
                cell = Table([
                    [Paragraph(_pdf_text(label), styles["SOWLabel"])],
                    [para(value)]
                ], colWidths=[col_width - 5*mm])
                cell.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,-1),pale),("BOX",(0,0),(-1,-1),0.4,grid),
                    ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
                    ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
                ]))
                row.append(cell)
            while len(row) < cols:
                row.append("")
            rows.append(row)
        table = Table(rows, colWidths=[usable_width/cols]*cols, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),
            ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ]))
        return table

    def data_table(headers, rows, widths):
        data = [[Paragraph(html.escape(str(h)), styles["SOWTableHeader"]) for h in headers]]
        data += [[para(value) for value in row] for row in rows]
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),navy),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),0.45,grid),("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F8F9FB")]),
        ]))
        return table

    story = []
    sow_logo = os.path.join(app.static_folder, "sow_logo.png")
    intact_logo = os.path.join(app.static_folder, "intact_logo.png")
    header_cells, header_widths = [], []
    if os.path.isfile(sow_logo):
        header_cells.append(Image(sow_logo, width=25*mm, height=23*mm, kind="proportional"))
        header_widths.append(29*mm)
    header_cells.append([
        Paragraph("STATEMENT OF WORK", styles["SOWTitle"]),
        Paragraph("<b>" + _pdf_text(project.project_name) + "</b>", styles["SOWSub"]),
        Paragraph(
            f"{_pdf_text(project.project_code)}  ·  Region: {_pdf_text(project.region)}  ·  Version: {_pdf_text(project.sow_version or 'V1')}",
            styles["SOWSub"])
    ])
    header_widths.append(usable_width - (29*mm if os.path.isfile(sow_logo) else 0)
                         - (29*mm if os.path.isfile(intact_logo) else 0))
    if os.path.isfile(intact_logo):
        header_cells.append(Image(intact_logo, width=24*mm, height=22*mm, kind="proportional"))
        header_widths.append(29*mm)
    header = Table([header_cells], colWidths=header_widths)
    header.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LINEBELOW",(0,0),(-1,-1),2,gold),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),9),
    ]))
    story += [header, Spacer(1,8)]

    # Keep the same six-section order and fields as templates/print.html.
    story += [section("01 · Project details"), info_grid([
        ("Project code",project.project_code),("Project name",project.project_name),
        ("Project team",project.project_team),("Project type",project.project_type),
        ("Start date",project.start_date),("End date",project.end_date),
        ("No. of FTEs",project.fte_count),("Region",project.region),
        ("Client name",project.client_name),("Business lead",project.business_lead),
        ("Lead designation",project.business_lead_designation),("Lead email",project.business_lead_email),
        ("Billing model",project.billing_model),("Change effective date",project.change_effective_date),
    ])]

    if project.change_summary:
        story += [section(f"Change summary · Version {project.sow_version or 'V1'}"),
                  para(project.change_summary,"SOWRich",rich=True)]

    story += [section("02 · Cost & billing"), data_table(
        ["Cost item","Basis","Amount (INR)","Currency","FX rate","Amount (FX)"],
        [["Project","Cost per month",project.project_cost_inr,project.billing_currency,project.fx_rate,project.project_cost_fx],
         ["Travel","As applicable",project.travel_cost_inr,project.travel_currency,project.travel_fx_rate,project.travel_cost_fx]],
        [34*mm,38*mm,37*mm,27*mm,27*mm,37*mm]),
        Spacer(1,5), para(f"Already part of an agreed FTE arrangement: {project.already_agreed_fte}","SOWSub")]

    resource_rows = [[r.name,r.billing_level,r.team,f"{r.allocation_percent or 0}%",
                      r.start_date,r.end_date,r.responsibilities] for r in project.resources]
    story += [section("03 · Resource plan"), data_table(
        ["Name","Billing level","Team","Allocation","Start date","End date","Role & responsibilities"],
        resource_rows or [["—","—","—","—","—","—","No resources provided."]],
        [32*mm,28*mm,27*mm,22*mm,25*mm,25*mm,65*mm])]

    milestone_rows = [[m.milestone,m.action_points,m.start_date,m.end_date,m.description]
                      for m in project.milestones]
    story += [section("04 · Milestones & activities"), data_table(
        ["Milestone","Action points","Start date","End date","Description"],
        milestone_rows or [["—","—","—","—","No milestones provided."]],
        [38*mm,43*mm,28*mm,28*mm,87*mm])]

    story.append(section("05 · Background & scope"))
    for title, value in [("Executive summary",project.executive_summary),("Background",project.background),
                         ("In scope",project.in_scope),("Out of scope",project.out_of_scope)]:
        if value:
            story += [Paragraph(html.escape(title),styles["SOWSubheading"]),
                      para(value,"SOWRich",rich=True)]

    story.append(section("06 · Risks, skills & requirements"))
    for title, value in [("Dependencies & risks",project.dependencies_risks),
                         ("Required skills",project.required_skills),
                         ("Software / versions required",project.software_required),
                         ("Other notes",project.other_notes),("Declarations",project.declarations)]:
        if value:
            story += [Paragraph(html.escape(title),styles["SOWSubheading"]),
                      para(value,"SOWRich",rich=True)]

    story += [Spacer(1,12), Paragraph(
        f"Generated from SOW Project Workspace · Record #{project.id} · Created "
        f"{project.created_at.strftime('%d %b %Y %H:%M UTC') if project.created_at else '—'}",
        styles["SOWFooter"])]

    def draw_page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(gold)
        canvas.setLineWidth(0.6)
        canvas.line(15*mm,10*mm,page_width-15*mm,10*mm)
        canvas.setFont("Helvetica",7)
        canvas.setFillColor(colors.HexColor("#687386"))
        canvas.drawRightString(page_width-15*mm,6*mm,
                               f"SOW · {project.project_code} · Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(output_path,pagesize=landscape(A4),
        rightMargin=15*mm,leftMargin=15*mm,topMargin=12*mm,bottomMargin=15*mm,
        title=f"{project.project_code} - Statement of Work",author="SOW Project Workspace")
    doc.build(story,onFirstPage=draw_page,onLaterPages=draw_page)
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
    edit_id = (project.edit_project_id or "").strip()
    current = db.session.get(SowProject, int(edit_id)) if edit_id.isdigit() else None
    suggested_version = next_sow_version(current.sow_version if current else None)
    return render_template("print.html", project=project, preview_mode=True,
                           suggested_version=suggested_version)


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

    if not confirmation_summary or confirmation_code != expected_code:
        project = _preview_object(draft)
        return render_template(
            "print.html", project=project, preview_mode=True,
            confirmation_error=(
                "Enter a change summary and confirm the project code. "
                "No database record or PDF has been created yet."
            ),
            modal_open=True, suggested_version=(next_sow_version(db.session.get(SowProject, project_id).sow_version) if project_id is not None else "V1"),
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
    if existing_project is not None and existing_project.active_flag != "Y":
        latest = (SowProject.query.filter_by(project_code=existing_project.project_code, active_flag="Y")
                  .order_by(SowProject.id.desc()).first())
        flash("Only the active SOW version can be edited. Opened the latest active version.", "error")
        return redirect(url_for("edit_project", project_id=latest.id)) if latest else redirect(url_for("list_projects"))
    # Version history is append-only: edits create a new project row; the prior row is deactivated.
    project = SowProject()
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
    project.sow_version = next_sow_version(existing_project.sow_version if existing_project else None)
    project.active_flag = "Y"
    project.change_summary = clean_rich_text(confirmation_summary)
    if existing_project is not None:
        existing_project.active_flag = "N"
        # Retain old resource rows for history, but mark the previous version's rows inactive.
        for old_resource in existing_project.resources:
            old_resource.active_flag = "N"

    try:
        db.session.add(project)
        db.session.flush()

        def val(name, index, default=""):
            items = draft.get(name, [])
            return items[index] if index < len(items) else default

        for i, name in enumerate(draft.get("resource_name[]", [])):
            if not name.strip():
                continue
            employee_id = val("resource_employee_id[]", i).strip()
            if not employee_id:
                raise ValueError(f"Employee ID is required for resource: {name.strip()}")
            project.resources.append(SowResource(
                employee_id=employee_id,
                active_flag="Y",
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
        action_word = "new version created" if existing_project is not None else "created"
        flash(f"SOW {action_word} ({project.sow_version}). Previous version is retained as inactive. PDF generated automatically: {pdf_filename}", "success")
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
    pdf_filename = f"{re.sub(r'[^A-Za-z0-9_-]+', '_', project.project_code or 'SOW')}_{project.id}.pdf"
    return send_from_directory(os.path.join(app.instance_path, "generated_pdfs"),
                               pdf_filename, as_attachment=True,
                               download_name=pdf_filename)


@app.route("/admin/pdf/genrate/<projectCode>", methods=["GET"])
def admin_generate_pdf(projectCode):
    """
    Generate a fresh PDF from the database record matching projectCode.
    Prefer the active SOW version; if none is marked active, use the latest record.
    """
    normalized_code = (projectCode or "").strip()
    if not normalized_code:
        return {"error": "Project code is required."}, 400

    project = (
        SowProject.query
        .filter(db.func.lower(SowProject.project_code) == normalized_code.lower(),
                SowProject.active_flag == "Y")
        .order_by(SowProject.id.desc())
        .first()
    )

    if project is None:
        project = (
            SowProject.query
            .filter(db.func.lower(SowProject.project_code) == normalized_code.lower())
            .order_by(SowProject.id.desc())
            .first()
        )

    if project is None:
        return {"error": f"No SOW record found for project code '{normalized_code}'."}, 404

    try:
        # Uses the same ReportLab generator, branding, page layout and styling
        # as the application's saved SOW PDF workflow.
        pdf_filename = generate_project_pdf(project)
        return send_from_directory(
            os.path.join(app.instance_path, "generated_pdfs"),
            pdf_filename,
            as_attachment=True,
            download_name=pdf_filename,
            mimetype="application/pdf"
        )
    except Exception as exc:
        app.logger.exception("Admin PDF generation failed for project code %s", normalized_code)
        return {"error": "PDF generation failed.", "details": str(exc)}, 500


def _resolve_sow_entry(entry_id):
    """Resolve a SOW by numeric database ID or by project code (active version first)."""
    key = (entry_id or "").strip()
    if key.isdigit():
        project = db.session.get(SowProject, int(key))
        if project is not None:
            return project
    project = (
        SowProject.query
        .filter(db.func.lower(SowProject.project_code) == key.lower(),
                SowProject.active_flag == "Y")
        .order_by(SowProject.id.desc())
        .first()
    )
    if project is None:
        project = (
            SowProject.query
            .filter(db.func.lower(SowProject.project_code) == key.lower())
            .order_by(SowProject.id.desc())
            .first()
        )
    return project


@app.route("/statementofwork/view/<string:EntryId>", methods=["GET"])
def project_view(EntryId):
    """Show a branded PDF workspace for a saved SOW record."""
    project = _resolve_sow_entry(EntryId)
    if project is None:
        return {"error": f"No SOW record found for '{EntryId}'."}, 404

    pdf_filename = f"{re.sub(r'[^A-Za-z0-9_-]+', '_', project.project_code or 'SOW')}_{project.id}.pdf"
    pdf_path = os.path.join(app.instance_path, "generated_pdfs", pdf_filename)
    if not os.path.isfile(pdf_path):
        try:
            generate_project_pdf(project)
        except Exception as exc:
            app.logger.exception("Could not generate PDF for SOW %s", EntryId)
            return {"error": "PDF generation failed.", "details": str(exc)}, 500

    return render_template(
        "pdf_viewer.html",
        project=project,
        pdf_filename=pdf_filename,
        pdf_url=url_for("project_pdf", EntryId=project.id),
        download_url=url_for("download_project_pdf", project_id=project.id),
        print_url=url_for("print_project", project_id=project.id),
    )


@app.route("/statementofwork/pdf/<string:EntryId>", methods=["GET"])
def project_pdf(EntryId):
    """Serve the ReportLab PDF inline for the branded PDF viewer."""
    project = _resolve_sow_entry(EntryId)
    if project is None:
        return {"error": f"No SOW record found for '{EntryId}'."}, 404

    pdf_filename = f"{re.sub(r'[^A-Za-z0-9_-]+', '_', project.project_code or 'SOW')}_{project.id}.pdf"
    pdf_dir = os.path.join(app.instance_path, "generated_pdfs")
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    if not os.path.isfile(pdf_path):
        try:
            generate_project_pdf(project)
        except Exception as exc:
            app.logger.exception("Could not generate inline PDF for SOW %s", EntryId)
            return {"error": "PDF generation failed.", "details": str(exc)}, 500

    return send_from_directory(
        pdf_dir, pdf_filename, mimetype="application/pdf",
        as_attachment=False, download_name=pdf_filename,
        max_age=0
    )


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
        with db.engine.begin() as conn:
            if "team" not in columns:
                conn.execute(text("ALTER TABLE sow_resources ADD COLUMN team VARCHAR(100) NULL"))
            if "employee_id" not in columns:
                conn.execute(text("ALTER TABLE sow_resources ADD COLUMN employee_id VARCHAR(50) NOT NULL DEFAULT ''"))
            if "active_flag" not in columns:
                conn.execute(text("ALTER TABLE sow_resources ADD COLUMN active_flag VARCHAR(3) NOT NULL DEFAULT 'Y'"))

    added_project_active_flag = False
    if "sow_projects" in tables:
        columns = {c["name"] for c in inspector.get_columns("sow_projects")}
        for name, sql_type in [
            ("sow_version", "VARCHAR(30) NOT NULL DEFAULT 'V1'"),
            ("active_flag", "VARCHAR(1) NOT NULL DEFAULT 'Y'"),
            ("change_summary", "TEXT NULL"),
            ("milestones_json", "TEXT NULL"),
        ]:
            if name not in columns:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE sow_projects ADD COLUMN {name} {sql_type}"))
                if name == "active_flag":
                    added_project_active_flag = True

    # One-time backfill only when adding the new active flag to an older database.
    # Do not run this on every request: later version status is managed by the save operation.
    if added_project_active_flag:
        with db.engine.begin() as conn:
            conn.execute(text("UPDATE sow_projects SET sow_version = 'V1' WHERE sow_version IS NULL OR sow_version = '' OR sow_version = '1.0'"))
            conn.execute(text("UPDATE sow_projects SET active_flag = 'N' WHERE id NOT IN (SELECT MAX(id) FROM sow_projects GROUP BY project_code)"))
            conn.execute(text("UPDATE sow_projects SET active_flag = 'Y' WHERE id IN (SELECT MAX(id) FROM sow_projects GROUP BY project_code)"))

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
