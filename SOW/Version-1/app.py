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
# SQLite is used for a quick local demo when DATABASE_URL is not configured.
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///sow_demo.db"
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

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    resources = db.relationship(
        "SowResource", backref="project", cascade="all, delete-orphan",
        order_by="SowResource.sort_order"
    )
    milestones = db.relationship(
        "SowMilestone", backref="project", cascade="all, delete-orphan",
        order_by="SowMilestone.sort_order"
    )


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


class SowMilestone(db.Model):
    __tablename__ = "sow_milestones"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("sow_projects.id"), nullable=False)
    milestone = db.Column(db.String(150), nullable=False)
    action_points = db.Column(db.Integer, default=1)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    description = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)


DEFAULT_DATA = {
    "project_code": "P0681",
    "project_name": "U&P BAU Change",
    "project_team": "Analytics",
    "project_type": "Continuous support",
    "start_date": "2025-01-01",
    "end_date": "",
    "fte_count": "27.25",
    "region": "UK&I",
    "client_name": "",
    "business_lead": "Andrew Hall",
    "business_lead_designation": "Technical Delivery Lead",
    "business_lead_email": "",
    "billing_model": "Fixed - FTE",
    "change_effective_date": "2026-10-01",
    "already_agreed_fte": "No",
    "project_cost_inr": "9778651.49",
    "billing_currency": "GBP",
    "fx_rate": "120",
    "project_cost_fx": "81488.76",
    "travel_cost_inr": "0",
    "travel_currency": "NA",
    "travel_fx_rate": "0",
    "travel_cost_fx": "0",
    "executive_summary": "Intact India resources support PVLR build and maintenance, RADAR base and live models, Risk Modeling, and other programme objectives as required.",
    "background": "Pricing View of Loss Ratio (PVLR) was added as a workstream in 2022 to create an efficient process for pricing views where unavailable and enable comparisons across portfolios. RADAR is a strategic rating tool for UK CL and EU. The India team supports RADAR development, maintenance and price-accuracy testing, and provides resources and technical guidance for the Keystone model.",
    "in_scope": "PVLR build and maintenance\\nRADAR re-scorer build\\nRADAR Live build and maintenance\\nRADAR Live price testing and test-case generation\\nSupport Keystone model building within Risk Modeling\\nSupport other Pricing Sophistication projects",
    "out_of_scope": "",
    "dependencies_risks": "Dependencies: Pricing consultants and portfolio leads provide subject-matter and KPI inputs. Teams collaborate to define PVLR and rescoring requirements and validate data-mart data. Business queries should be resolved promptly.\\nRisks: Client data transfers must comply with applicable data-protection laws. Share only necessary personal data, pseudonymise/anonymise where applicable, use secure transfer methods, and report suspected incidents immediately.",
    "required_skills": "People skills for stakeholder meetings and KPI agreement\\nInsurance KPIs: top-line, conversion, WLR, RMI indices and rating strength\\nSAS/WPS coding and data handling\\nRADAR model build and monitoring\\nTranslate business requirements into tasks\\nMicrosoft Excel, VBA, pricing flows and claims development",
    "software_required": "SAS\\nExcel\\nRADAR\\nTeams\\nSharePoint\\nCQE\\nMicrosoft Office 365",
    "other_notes": "Project billed on a full-time employee basis. Monthly feedback meeting between project manager and business lead. Two months' written notice is required for service termination. Actual invoice is in INR; GBP values may vary with FX movement.",
    "declarations": "1. Responsibility for compliance with local data-protection rules and regulations lies with the local businesses as mentioned in the Technical Service Level Agreements.\\n2. Intact India retains relevant files for up to 2 years. The business should arrange longer retention if required."
}

DEFAULT_RESOURCES = [
    ("Aashi Gupta","Consultant",100,"2025-01-01","2026-12-31","PVLR build and maintenance"),
    ("Apoorva Srivastava","Consultant",100,"2025-01-01","2026-12-31","Data mart testing and building support"),
    ("Bhoomi Agrawal","Consultant",100,"2025-01-01","2026-12-31","Data mart testing and building support"),
    ("Debarshi Datta","Head",50,"2025-01-01","2026-12-31","Data mart testing and building support"),
    ("Diksha Kapoor","Consultant",100,"2025-01-01","2026-12-31","RADAR re-scorer build"),
    ("Divya Singh","Consultant",100,"2025-01-01","2026-12-31","Data mart testing and building support"),
    ("Gavika Taneja","Consultant",100,"2025-01-01","2026-12-31","PVLR build and maintenance"),
    ("Hansika Singh","Head",75,"2025-01-01","2026-12-31","PVLR build and maintenance"),
    ("Manit Gupta","Consultant",100,"2025-01-01","2026-12-31","PVLR build and maintenance"),
    ("Richa Upadhyay","Manager",100,"2025-01-01","2026-12-31","RADAR emulator"),
    ("Srishti Grover","Consultant",100,"2025-01-01","2026-12-31","PVLR build and maintenance"),
    ("Vaibhav Sharma","Consultant",100,"2025-01-01","2026-12-31","Data mart testing and building support"),
    ("Itika Singal","Consultant",100,"2025-04-01","2026-12-31","Risk Modeling"),
    ("M Madhumitha","Consultant",100,"2025-04-01","2026-12-31","RADAR Emulator"),
    ("Torambe Rutik Jayram","Analyst",100,"2025-08-01","2026-12-31","Price Testing"),
    ("Sumit Taneja","Analyst",100,"2025-08-15","2026-12-31","Price Testing"),
    ("Harshit Chhatwala","Analyst",100,"2025-09-01","2026-12-31","PVLR build and maintenance"),
    ("Rudraksha Khatri","Senior Consultant",100,"2025-09-01","2026-12-31","Price Testing"),
    ("Vanshika Kapoor","Analyst",100,"2025-09-01","2026-12-31","PVLR build and maintenance"),
    ("Unnati Sharma","",100,"2025-11-07","2026-12-31","RADAR Emulator"),
    ("Sushant Makkar","",100,"2025-12-17","2026-12-31","PVLR Lead"),
    ("Bhavya Choudhary","Consultant",100,"2026-04-01","2026-12-31","Transformation"),
    ("Cherry Chhabra","Consultant",100,"2026-04-01","2026-12-31","1C Motor"),
    ("Shivam Khurana","Senior Consultant",100,"2026-07-01","2026-12-31","RADAR Dev"),
    ("Govind Swami","Analyst",100,"2026-09-01","2026-12-31","RADAR Emulator"),
    ("Komalpreet Kaur","Analyst",100,"2026-09-01","2026-12-31","RADAR Emulator"),
    ("Taran Gaur","Analyst",100,"2026-09-01","2026-12-31","Transformation"),
    ("Varun Valecha","Analyst",100,"2026-09-01","2026-12-31","RADAR Emulator"),
    ("Divye Kalra","Analyst",100,"2026-10-01","2026-12-31","RADAR Resource"),
    ("Riddhi Rupda","Analyst",100,"2026-10-01","2026-12-31","RADAR Resource"),
]
DEFAULT_MILESTONES = [
    ("Planning",1,"2025-01-01","2026-12-31","SOW and monthly calls"),
    ("Project Training",1,"2025-01-01","2026-12-31","Portfolio training, RADAR and SAS"),
    ("Data",1,"2025-01-01","2026-12-31","Data build for Quotes/Policy/Claims as required"),
    ("Analysis",1,"2025-01-01","2026-12-31","Data analysis and other ad-hoc work"),
    ("Meeting",1,"2025-01-01","2026-12-31","Regular calls with business lead, BA and stakeholders"),
    ("Peer Review",0,"2025-01-01","2026-12-31","No peer review from IA"),
    ("Report & Documentation",1,"2025-01-01","2026-12-31","Emails and dashboard documentation"),
]


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


def get_form_data():
    data = DEFAULT_DATA.copy()
    data.update(request.form.to_dict())
    return data


@app.route("/")
def index():
    # Start a new form with the sample data. The browser back button can return from preview.
    return render_template(
        "form.html", data=DEFAULT_DATA, resources=DEFAULT_RESOURCES,
        milestones=DEFAULT_MILESTONES
    )



def _draft_values():
    """Read the pending preview draft from server-side storage."""
    token = session.get("sow_draft_token")
    if not token:
        return {}
    draft_path = os.path.join(app.instance_path, "drafts", f"{token}.json")
    if not os.path.isfile(draft_path):
        return {}
    try:
        with open(draft_path, "r", encoding="utf-8") as draft_file:
            return json.load(draft_file)
    except (OSError, ValueError):
        return {}


def _draft_scalar_values(draft):
    return {key: (values[-1] if isinstance(values, list) and values else "")
            for key, values in draft.items()}


def _preview_object(draft):
    values = _draft_scalar_values(draft)
    data = DEFAULT_DATA.copy()
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
        sow_version=values.get("sow_version", "1.0"),
        change_summary=clean_rich_text(values.get("change_summary", "")),
        resources=resources, milestones=milestones
    )


def generate_project_pdf(project):
    """Generate a PDF on the server and return its filename."""
    output_dir = os.path.join(app.instance_path, "generated_pdfs")
    os.makedirs(output_dir, exist_ok=True)
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", project.project_code or "SOW")
    filename = f"{safe_code}_{project.id}.pdf"
    output_path = os.path.join(output_dir, filename)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SowTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                              fontSize=19, leading=23, textColor=colors.HexColor("#35245e"), alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="SowSection", parent=styles["Heading2"], fontSize=12, leading=15,
                              textColor=colors.HexColor("#35245e"), spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="SowBody", parent=styles["BodyText"], fontSize=8.5, leading=11, spaceAfter=4))
    styles.add(ParagraphStyle(name="SowSmall", parent=styles["BodyText"], fontSize=7, leading=9))
    story = [
        Paragraph("STATEMENT OF WORK", styles["SowSmall"]),
        Paragraph(html.escape(project.project_name or "Untitled SOW"), styles["SowTitle"]),
        Paragraph(f"Project code: {html.escape(str(project.project_code or '—'))} &nbsp; | &nbsp; Region: {html.escape(str(project.region or '—'))}", styles["SowBody"]),
        Spacer(1, 4*mm),
    ]

    def fmt(value):
        if value is None or str(value).strip() == "":
            return "—"
        if isinstance(value, (date, datetime)):
            return value.strftime("%d-%b-%Y")
        return str(value)

    def add_section(title, rows):
        story.append(Paragraph(html.escape(title), styles["SowSection"]))
        table = Table([[Paragraph(f"<b>{html.escape(str(k))}</b>", styles["SowSmall"]),
                        Paragraph(html.escape(fmt(v)), styles["SowSmall"])] for k, v in rows],
                      colWidths=[48*mm, 220*mm], repeatRows=0)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f0edf8")),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#d8d4e3")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(table)
        story.append(Spacer(1, 2*mm))

    def add_rich_section(title, value):
        if not value:
            return
        story.append(Paragraph(html.escape(title), styles["SowSection"]))
        # ReportLab Paragraph supports a safe subset of HTML; sanitize and convert common tags.
        content = value.replace("<p", "<para").replace("</p>", "</para>")
        content = re.sub(r'<(h[23])[^>]*>', '<b>', content, flags=re.I)
        content = re.sub(r'</h[23]>', '</b><br/>', content, flags=re.I)
        content = re.sub(r'<span[^>]*>', '', content, flags=re.I).replace("</span>", "")
        content = content.replace("<div>", "").replace("</div>", "<br/>")
        content = content.replace("<blockquote>", "<i>").replace("</blockquote>", "</i><br/>")
        content = re.sub(r"""<a[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", r'<link href="\1" color="blue">\2</link>', content, flags=re.I)
        # Keep only tags ReportLab can parse, stripping style attributes and Quill classes.
        content = re.sub(r'<(p|para|strong|b|em|i|u|ol|ul|li|br)(?:\s+[^>]*)?>', lambda m: "<" + m.group(1).lower() + ">", content, flags=re.I)
        content = re.sub(r'<(?!/?(?:para|strong|b|em|i|u|ol|ul|li|br|link)\b)[^>]+>', '', content, flags=re.I)
        content = content.replace("&nbsp;", " ").replace("&#39;", "'")
        if not content.strip():
            return
        try:
            story.append(Paragraph(content, styles["SowBody"]))
        except Exception:
            plain = re.sub(r"<[^>]+>", " ", content)
            story.append(Paragraph(html.escape(plain), styles["SowBody"]))

    add_section("01 · Project details", [
        ("Project code", project.project_code), ("Project name", project.project_name),
        ("Project team", project.project_team), ("Project type", project.project_type),
        ("Start date", project.start_date), ("End date", project.end_date),
        ("No. of FTEs", project.fte_count), ("Region", project.region),
        ("Client name", project.client_name), ("Business lead", project.business_lead),
        ("Lead designation", project.business_lead_designation), ("Lead email", project.business_lead_email),
        ("Billing model", project.billing_model), ("Change effective date", project.change_effective_date),
        ("SOW version", getattr(project, "sow_version", "1.0")),
    ])
    add_rich_section("Change summary", getattr(project, "change_summary", ""))
    add_section("02 · Cost & billing", [
        ("Project cost (INR)", project.project_cost_inr), ("Billing currency", project.billing_currency),
        ("FX rate", project.fx_rate), ("Project amount (FX)", project.project_cost_fx),
        ("Travel cost (INR)", project.travel_cost_inr), ("Travel currency", project.travel_currency),
        ("Travel FX rate", project.travel_fx_rate), ("Travel amount (FX)", project.travel_cost_fx),
        ("Already agreed FTE arrangement", project.already_agreed_fte),
    ])

    def add_grid_table(title, headers, rows):
        story.append(Paragraph(html.escape(title), styles["SowSection"]))
        data = [[Paragraph(f"<b>{html.escape(str(h))}</b>", styles["SowSmall"]) for h in headers]]
        for row in rows:
            data.append([Paragraph(html.escape(fmt(v)), styles["SowSmall"]) for v in row])
        if len(data) == 1:
            data.append([Paragraph("No records provided", styles["SowSmall"])] + [Paragraph("", styles["SowSmall"]) for _ in headers[1:]])
        widths = [268*mm / len(headers)] * len(headers)
        table = Table(data, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#35245e")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#d8d4e3")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(table)
        story.append(Spacer(1, 2*mm))

    add_grid_table("03 · Resource plan",
        ["Name", "Billing level", "Team", "Allocation", "Start", "End", "Responsibilities"],
        [[r.name, r.billing_level, r.team, f"{fmt(r.allocation_percent)}%", r.start_date, r.end_date, r.responsibilities] for r in project.resources])
    add_grid_table("04 · Milestones & activities",
        ["Milestone", "Action points", "Start", "End", "Description"],
        [[m.milestone, m.action_points, m.start_date, m.end_date, m.description] for m in project.milestones])

    for title, value in [
        ("05 · Executive summary", project.executive_summary), ("Background", project.background),
        ("In scope", project.in_scope), ("Out of scope", project.out_of_scope),
        ("06 · Dependencies & risks", project.dependencies_risks), ("Required skills", project.required_skills),
        ("Software required", project.software_required), ("Other notes", project.other_notes),
        ("Declarations", project.declarations),
    ]:
        add_rich_section(title, value)

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(14*mm, 7*mm, f"SOW {project.project_code} · Record {project.id}")
        canvas.drawRightString(283*mm, 7*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                            rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=12*mm, bottomMargin=13*mm,
                            title=f"{project.project_code} - {project.project_name}")
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return filename


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


@app.route("/projects", methods=["POST"])
def create_project():
    # The confirmation is a required server-side gate, not just browser validation.
    # Nothing is added to the database until both fields pass validation.
    draft_token = session.get("sow_draft_token")
    draft = _draft_values()
    if not draft or not draft_token:
        flash("Your preview has expired. Please review the SOW again before saving.", "error")
        return redirect(url_for("index"))

    values = _draft_scalar_values(draft)
    data = DEFAULT_DATA.copy()
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

    project = SowProject(
        project_code=data.get("project_code", "").strip(),
        project_name=data.get("project_name", "").strip(),
        project_team=data.get("project_team"),
        project_type=data.get("project_type"),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        fte_count=parse_decimal(data.get("fte_count")),
        region=data.get("region"),
        client_name=data.get("client_name"),
        business_lead=data.get("business_lead"),
        business_lead_designation=data.get("business_lead_designation"),
        business_lead_email=data.get("business_lead_email"),
        billing_model=data.get("billing_model"),
        change_effective_date=parse_date(data.get("change_effective_date")),
        already_agreed_fte=data.get("already_agreed_fte"),
        project_cost_inr=parse_decimal(data.get("project_cost_inr")),
        billing_currency=data.get("billing_currency"),
        fx_rate=parse_decimal(data.get("fx_rate")),
        project_cost_fx=parse_decimal(data.get("project_cost_fx")),
        travel_cost_inr=parse_decimal(data.get("travel_cost_inr")),
        travel_currency=data.get("travel_currency"),
        travel_fx_rate=parse_decimal(data.get("travel_fx_rate")),
        travel_cost_fx=parse_decimal(data.get("travel_cost_fx")),
        executive_summary=clean_rich_text(data.get("executive_summary")),
        background=clean_rich_text(data.get("background")),
        in_scope=clean_rich_text(data.get("in_scope")),
        out_of_scope=clean_rich_text(data.get("out_of_scope")),
        dependencies_risks=clean_rich_text(data.get("dependencies_risks")),
        required_skills=clean_rich_text(data.get("required_skills")),
        software_required=clean_rich_text(data.get("software_required")),
        other_notes=clean_rich_text(data.get("other_notes")),
        declarations=clean_rich_text(data.get("declarations")),
        sow_version=confirmation_version,
        change_summary=clean_rich_text(confirmation_summary),
    )

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

        for i, name in enumerate(draft.get("milestone_name[]", [])):
            if not name.strip():
                continue
            try:
                action_points = int(val("milestone_points[]", i, "0") or 0)
            except ValueError:
                action_points = 0
            project.milestones.append(SowMilestone(
                milestone=name.strip(), action_points=action_points,
                start_date=parse_date(val("milestone_start[]", i)),
                end_date=parse_date(val("milestone_end[]", i)),
                description=val("milestone_description[]", i),
                sort_order=i,
            ))

        # Required order: validate confirmation -> stage DB objects -> generate PDF ->
        # commit DB. If PDF generation fails, the transaction is rolled back and no SOW
        # record is committed. If DB commit fails, remove the already-generated PDF.
        pdf_filename = generate_project_pdf(project)
        pdf_path = os.path.join(app.instance_path, "generated_pdfs", pdf_filename)
        try:
            db.session.commit()
        except Exception:
            # Avoid leaving a PDF behind if the database commit fails.
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
        flash(f"SOW saved. PDF generated automatically: {pdf_filename}", "success")
        return redirect(url_for("print_project", project_id=project.id, saved=1))
    except Exception as exc:
        db.session.rollback()
        app.logger.exception("Could not save SOW project or generate PDF")
        flash("Could not save the SOW or generate the PDF. Check the database and PDF dependencies. Details: " + str(exc), "error")
        return render_template("form.html", data=data, resources=[], milestones=[]), 500


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


@app.route("/health")
def health():
    return {"status": "ok"}


def ensure_schema():
    """Create missing tables and add new nullable columns to existing demo databases."""
    db.create_all()
    inspector = db.inspect(db.engine)
    if "sow_resources" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("sow_resources")}
        if "team" not in existing:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE sow_resources ADD COLUMN team VARCHAR(100) NULL"))
    if "sow_projects" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("sow_projects")}
        dialect = db.engine.dialect.name
        for column_name, column_sql in [
            ("sow_version", "VARCHAR(30) NOT NULL DEFAULT '1.0'"),
            ("change_summary", "TEXT NULL"),
        ]:
            if column_name not in existing:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE sow_projects ADD COLUMN {column_name} {column_sql}"))


@app.before_request
def initialize_schema_for_demo():
    # Keeps older local SQLite databases usable after adding fields to the model.
    ensure_schema()


if __name__ == "__main__":
    with app.app_context():
        ensure_schema()
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
