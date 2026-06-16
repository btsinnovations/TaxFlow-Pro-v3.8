"""
Engagement router: manage engagement letter templates and create
engagements from templates. Templates are stored in a local SQLite file.
"""
import os
import sqlite3
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(prefix="/engagements", tags=["engagement"])

ENGAGEMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
ENGAGEMENTS_DB = os.path.join(ENGAGEMENTS_DIR, "engagements.db")


class EngagementTemplateSummary(BaseModel):
    template_type: str
    name: str
    description: str


class EngagementTemplateDetail(BaseModel):
    template_type: str
    name: str
    description: str
    body: str
    default_fee: Optional[float] = None
    checklist_items: List[str]


class EngagementFromTemplateRequest(BaseModel):
    template_type: str
    client_id: int
    engagement_name: Optional[str] = None
    due_date: Optional[str] = None
    custom_fee: Optional[float] = None
    notes: Optional[str] = None


class EngagementFromTemplateResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    name: str
    description: str
    checklist: str
    due_date: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# Default templates
DEFAULT_TEMPLATES = [
    {
        "template_type": "tax_return_individual",
        "name": "Individual Tax Return Preparation",
        "description": "Preparation and filing of Form 1040 and associated schedules",
        "body": """ENGAGEMENT LETTER - INDIVIDUAL TAX RETURN

We are pleased to confirm our understanding of the services we will provide for the preparation of your individual income tax return for the year ending December 31, {year}.

SCOPE OF SERVICES:
- Review financial information and supporting documents
- Prepare Form 1040 and required schedules
- Calculate estimated tax payments for next year
- E-file or provide paper filing instructions

CLIENT RESPONSIBILITIES:
- Provide all required documents by the agreed deadline
- Notify us of any foreign accounts, assets, or income
- Review return for accuracy before signing

FEE: ${fee}

This engagement will conclude upon filing of the return.""",
        "default_fee": 850.00,
        "checklist_items": [
            "W-2 Forms", "1099 Forms", "Schedule K-1s", "Investment Statements",
            "Property Tax Statements", "Charitable Donation Receipts",
            "Medical Expense Receipts", "Bank Account Information",
            "Foreign Account Reporting", "Prior Year Return",
        ],
    },
    {
        "template_type": "tax_return_business",
        "name": "Business Tax Return Preparation",
        "description": "Preparation of Form 1065, 1120-S, or 1120 for business entities",
        "body": """ENGAGEMENT LETTER - BUSINESS TAX RETURN

We will prepare the {entity_type} tax return for {client_name} for the year ending {year_end}.

SCOPE OF SERVICES:
- Review bookkeeping records and journal entries
- Prepare business tax return (Form {form_number})
- Prepare Schedule K-1s for all partners/shareholders
- Review basis calculations
- E-file or prepare for paper filing

CLIENT RESPONSIBILITIES:
- Provide complete and accurate books by {deadline}
- Reconcile all bank and credit card accounts
- Provide vehicle mileage logs if applicable
- Review draft returns and K-1s

FEE: ${fee}""",
        "default_fee": 2500.00,
        "checklist_items": [
            "General Ledger", "Bank Statements", "Credit Card Statements",
            "Loan Documents", "Fixed Asset Records", "Payroll Reports",
            "1099s Issued", "Partner/Shareholder Info", "Prior Year Return",
            "State Filing Requirements",
        ],
    },
    {
        "template_type": "bookkeeping_monthly",
        "name": "Monthly Bookkeeping Services",
        "description": "Ongoing monthly bookkeeping and reconciliation services",
        "body": """ENGAGEMENT LETTER - MONTHLY BOOKKEEPING

We will provide monthly bookkeeping services for {client_name} beginning {start_date}.

SERVICES INCLUDE:
- Categorize and record transactions
- Reconcile bank and credit card accounts
- Prepare monthly financial statements
- Track accounts payable and receivable
- Quarterly sales tax preparation (if applicable)

MONTHLY FEE: ${fee}

This engagement is ongoing and may be terminated by either party with 30 days written notice.""",
        "default_fee": 500.00,
        "checklist_items": [
            "Bank Statements", "Credit Card Statements", "Receipts/Invoices",
            "Loan Payment Records", "Payroll Records", "Sales Reports",
            "Expense Reports", "Previous Month Reconciliation",
        ],
    },
    {
        "template_type": "payroll_processing",
        "name": "Payroll Processing Services",
        "description": "Full-service payroll processing and tax filing",
        "body": """ENGAGEMENT LETTER - PAYROLL SERVICES

We will process payroll for {client_name} on a {frequency} basis.

SERVICES INCLUDE:
- Calculate wages, deductions, and net pay
- Prepare and file payroll tax returns (941, 940, state)
- Issue W-2s and 1099-NECs
- New hire reporting
- Direct deposit processing

PER-PAYROLL FEE: ${fee}

Quarterly and annual reporting included.""",
        "default_fee": 150.00,
        "checklist_items": [
            "Employee Information", "Hourly Rates/Salaries",
            "Tax Withholding Forms (W-4)", "Benefit Deductions",
            "PTO Balances", "New Hire Paperwork",
        ],
    },
    {
        "template_type": "audit_review",
        "name": "Review Engagement / Compilation",
        "description": "Review or compilation of financial statements",
        "body": """ENGAGEMENT LETTER - REVIEW ENGAGEMENT

We will perform a review of the financial statements of {client_name} for the year ending {year_end}.

A review consists primarily of analytical procedures and inquiries of management.

Our report will state that we are not aware of any material modifications that should be made.

FEE: ${fee}

Please sign and return the attached representation letter.""",
        "default_fee": 5000.00,
        "checklist_items": [
            "Trial Balance", "General Ledger", "Bank Confirmations",
            "AR Aging", "AP Aging", "Inventory Records",
            "Loan Agreements", "Lease Agreements", "Minutes",
            "Subsequent Events Documentation",
        ],
    },
    {
        "template_type": "consulting",
        "name": "Tax Consulting / Advisory",
        "description": "Hourly tax consulting and advisory services",
        "body": """ENGAGEMENT LETTER - TAX CONSULTING

We will provide tax consulting services regarding: {topic}

SERVICES INCLUDE:
- Research relevant tax law and regulations
- Analyze alternative strategies
- Prepare memorandum of findings
- Recommend optimal approach

HOURLY RATE: ${fee}/hour

Estimated hours: {estimated_hours}

This is a time-and-materials engagement.""",
        "default_fee": 350.00,
        "checklist_items": [
            "Prior Correspondence", "Relevant Tax Documents",
            "Entity Documents", "Financial Projections",
            "Applicable Case Law or Rulings",
        ],
    },
]


def _init_engagements_db():
    os.makedirs(ENGAGEMENTS_DIR, exist_ok=True)
    conn = sqlite3.connect(ENGAGEMENTS_DB)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS engagement_templates (
            template_type TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            body TEXT NOT NULL,
            default_fee REAL,
            checklist_items TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS engagements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            template_type TEXT,
            name TEXT NOT NULL,
            description TEXT,
            checklist TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'draft',
            fee REAL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()

    # Seed default templates if not present
    for tmpl in DEFAULT_TEMPLATES:
        cur.execute(
            "SELECT 1 FROM engagement_templates WHERE template_type = ?",
            (tmpl["template_type"],),
        )
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO engagement_templates
                (template_type, name, description, body, default_fee, checklist_items)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tmpl["template_type"],
                    tmpl["name"],
                    tmpl["description"],
                    tmpl["body"],
                    tmpl["default_fee"],
                    "\n".join(tmpl["checklist_items"]),
                ),
            )
    conn.commit()
    conn.close()


def _get_template(template_type: str) -> Optional[dict]:
    _init_engagements_db()
    conn = sqlite3.connect(ENGAGEMENTS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM engagement_templates WHERE template_type = ?", (template_type,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["checklist_items"] = d.get("checklist_items", "").split("\n") if d.get("checklist_items") else []
        return d
    return None


def _list_templates() -> List[dict]:
    _init_engagements_db()
    conn = sqlite3.connect(ENGAGEMENTS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT template_type, name, description FROM engagement_templates ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/templates", response_model=List[EngagementTemplateSummary])
def list_templates(
    current_user: models.User = Depends(get_current_user),
):
    templates = _list_templates()
    return [
        EngagementTemplateSummary(
            template_type=t["template_type"],
            name=t["name"],
            description=t["description"],
        )
        for t in templates
    ]


@router.get("/templates/{template_type}", response_model=EngagementTemplateDetail)
def get_template(
    template_type: str,
    current_user: models.User = Depends(get_current_user),
):
    tmpl = _get_template(template_type)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return EngagementTemplateDetail(
        template_type=tmpl["template_type"],
        name=tmpl["name"],
        description=tmpl["description"],
        body=tmpl["body"],
        default_fee=tmpl.get("default_fee"),
        checklist_items=tmpl.get("checklist_items", []),
    )


@router.post("/from-template", status_code=status.HTTP_201_CREATED, response_model=EngagementFromTemplateResponse)
def create_from_template(
    req: EngagementFromTemplateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == req.client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    tmpl = _get_template(req.template_type)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template '{req.template_type}' not found")

    name = req.engagement_name or tmpl["name"]
    fee = req.custom_fee if req.custom_fee is not None else tmpl.get("default_fee", 0.0)
    checklist = "\n".join(tmpl.get("checklist_items", []))
    year = datetime.utcnow().year

    # Render template body with placeholders
    body = tmpl["body"].replace("{year}", str(year))
    body = body.replace("{client_name}", client.name)
    body = body.replace("{fee}", f"{fee:.2f}")

    _init_engagements_db()
    conn = sqlite3.connect(ENGAGEMENTS_DB)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO engagements
        (tenant_id, user_id, template_type, name, description, checklist, due_date, status, fee, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req.client_id,
            current_user.id,
            req.template_type,
            name,
            body,
            checklist,
            req.due_date,
            "draft",
            fee,
            req.notes,
        ),
    )
    conn.commit()
    engagement_id = cur.lastrowid

    cur.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
    row = cur.fetchone()
    conn.close()

    audit = models.AuditEntry(
        tenant_id=req.client_id,
        user_id=current_user.id,
        action="engagement_create_from_template",
        entity_type="engagement",
        entity_id=engagement_id,
        details=f"Created engagement '{name}' from template '{req.template_type}'",
    )
    db.add(audit)
    db.commit()

    return EngagementFromTemplateResponse(
        id=engagement_id,
        tenant_id=req.client_id,
        user_id=current_user.id,
        name=name,
        description=body,
        checklist=checklist,
        due_date=req.due_date,
        status="draft",
        created_at=datetime.strptime(row[11], "%Y-%m-%d %H:%M:%S") if row[11] else datetime.utcnow(),
    )
