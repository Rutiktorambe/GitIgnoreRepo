import os
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

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


def get_form_data():
    data = DEFAULT_DATA.copy()
    data.update(request.form.to_dict())
    return data


@app.route("/")
def index():
    return render_template(
        "form.html", data=DEFAULT_DATA, resources=DEFAULT_RESOURCES,
        milestones=DEFAULT_MILESTONES
    )


@app.route("/projects", methods=["POST"])
def create_project():
    data = get_form_data()
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
        executive_summary=data.get("executive_summary"),
        background=data.get("background"),
        in_scope=data.get("in_scope"),
        out_of_scope=data.get("out_of_scope"),
        dependencies_risks=data.get("dependencies_risks"),
        required_skills=data.get("required_skills"),
        software_required=data.get("software_required"),
        other_notes=data.get("other_notes"),
        declarations=data.get("declarations"),
    )

    try:
        db.session.add(project)
        db.session.flush()

        resource_names = request.form.getlist("resource_name[]")
        levels = request.form.getlist("resource_level[]")
        allocations = request.form.getlist("resource_allocation[]")
        starts = request.form.getlist("resource_start[]")
        ends = request.form.getlist("resource_end[]")
        responsibilities = request.form.getlist("resource_responsibilities[]")
        for i, name in enumerate(resource_names):
            if not name.strip():
                continue
            project.resources.append(SowResource(
                name=name.strip(),
                billing_level=levels[i] if i < len(levels) else "",
                allocation_percent=parse_decimal(allocations[i] if i < len(allocations) else "100"),
                start_date=parse_date(starts[i] if i < len(starts) else ""),
                end_date=parse_date(ends[i] if i < len(ends) else ""),
                responsibilities=responsibilities[i] if i < len(responsibilities) else "",
                sort_order=i,
            ))

        names = request.form.getlist("milestone_name[]")
        points = request.form.getlist("milestone_points[]")
        mstarts = request.form.getlist("milestone_start[]")
        mends = request.form.getlist("milestone_end[]")
        descriptions = request.form.getlist("milestone_description[]")
        for i, name in enumerate(names):
            if not name.strip():
                continue
            try:
                action_points = int(points[i]) if i < len(points) and points[i] else 0
            except ValueError:
                action_points = 0
            project.milestones.append(SowMilestone(
                milestone=name.strip(),
                action_points=action_points,
                start_date=parse_date(mstarts[i] if i < len(mstarts) else ""),
                end_date=parse_date(mends[i] if i < len(mends) else ""),
                description=descriptions[i] if i < len(descriptions) else "",
                sort_order=i,
            ))
        db.session.commit()
        return redirect(url_for("print_project", project_id=project.id))
    except Exception as exc:
        db.session.rollback()
        app.logger.exception("Could not save SOW project")
        flash("Could not save the SOW. Check your database connection and required fields. Details: " + str(exc), "error")
        return render_template("form.html", data=data, resources=[], milestones=[]), 500


@app.route("/projects/<int:project_id>/print")
def print_project(project_id):
    project = db.get_or_404(SowProject, project_id)
    return render_template("print.html", project=project)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
