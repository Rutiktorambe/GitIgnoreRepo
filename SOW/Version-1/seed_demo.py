"""Seed the configured SOW database with a demo project, resources and milestones.
Run: python seed_demo.py
Uses DATABASE_URL if configured; otherwise the app's default SQLite database.
Skips insertion if project code DEMO-1001 already exists.
"""
from datetime import date
from dotenv import load_dotenv
load_dotenv()

from app import app, db, SowProject, SowResource, SowMilestone

with app.app_context():
    db.create_all()
    project = SowProject.query.filter_by(project_code="DEMO-1001").first()
    if project:
        print(f"Demo project already exists (id={project.id}); no changes made.")
    else:
        project = SowProject(
            project_code="DEMO-1001", project_name="Customer Analytics SOW",
            project_team="Analytics", project_type="Continuous support",
            start_date=date(2026,1,1), end_date=date(2026,12,31), fte_count=5.5,
            region="India", client_name="Example Insurance Ltd.", business_lead="Priya Sharma",
            business_lead_designation="Delivery Lead", business_lead_email="priya.sharma@example.com",
            billing_model="Fixed - FTE", change_effective_date=date(2026,10,1),
            already_agreed_fte="No", project_cost_inr=2500000, billing_currency="INR",
            fx_rate=1, project_cost_fx=2500000, travel_cost_inr=25000,
            travel_currency="INR", travel_fx_rate=1, travel_cost_fx=25000,
            executive_summary="Provide analytics delivery support for reporting, data quality and model monitoring.",
            background="The project supports analytics operations and reporting enhancements across the policy lifecycle.",
            in_scope="Data quality checks\\nDashboard maintenance\\nMonthly reporting\\nModel monitoring",
            out_of_scope="New platform procurement and infrastructure support",
            dependencies_risks="Dependencies: stakeholders provide requirements and timely feedback. Risks: protect confidential data and restrict access to authorised staff.",
            required_skills="SQL, Python, Excel, dashboard development, data validation and stakeholder communication",
            software_required="Python\\nSQL Server\\nExcel\\nPower BI\\nMicrosoft Teams",
            other_notes="Monthly status meeting; estimates are subject to review and approval.",
            declarations="Demo record only. Replace all sample values before production use.",
        )
        project.resources = [
            SowResource(name="Aarav Mehta", billing_level="Consultant", allocation_percent=100,
                start_date=date(2026,1,1), end_date=date(2026,12,31),
                responsibilities="Data validation and reporting", sort_order=0),
            SowResource(name="Neha Patel", billing_level="Senior Analyst", allocation_percent=100,
                start_date=date(2026,1,1), end_date=date(2026,12,31),
                responsibilities="Dashboard development and analysis", sort_order=1),
            SowResource(name="Kabir Singh", billing_level="Analyst", allocation_percent=50,
                start_date=date(2026,4,1), end_date=date(2026,12,31),
                responsibilities="Data quality checks and documentation", sort_order=2),
        ]
        project.milestones = [
            SowMilestone(milestone="Planning", action_points=1, start_date=date(2026,1,1), end_date=date(2026,1,15), description="Confirm scope, stakeholders and delivery cadence", sort_order=0),
            SowMilestone(milestone="Data assessment", action_points=2, start_date=date(2026,1,16), end_date=date(2026,2,15), description="Review source data and establish quality checks", sort_order=1),
            SowMilestone(milestone="Dashboard delivery", action_points=3, start_date=date(2026,2,16), end_date=date(2026,4,30), description="Build and validate reporting dashboards", sort_order=2),
            SowMilestone(milestone="Monthly reporting", action_points=12, start_date=date(2026,5,1), end_date=date(2026,12,31), description="Publish monthly reporting pack and status updates", sort_order=3),
        ]
        db.session.add(project)
        db.session.commit()
        print(f"Inserted demo project (id={project.id}), 3 resources and 4 milestones.")
