"""
Tax rules endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import List
from api_models import TaxRuleOut, TaxRuleUpdate
from api_utils import get_db, save_db, log_event

DEFAULT_RULES = [
    {"id": "tr1", "name": "Vehicle Fuel", "keyword": "fuel", "category": "fuel_expense", "schedule_line": "[Car and Truck Expenses (Line 9)]", "deductible": True, "entity_types": ["Individual", "LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr2", "name": "Gas Station", "keyword": "gas", "category": "fuel_expense", "schedule_line": "[Car and Truck Expenses (Line 9)]", "deductible": True, "entity_types": ["Individual", "LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr3", "name": "Office Supplies", "keyword": "office supplies", "category": "office_expense", "schedule_line": "[Office Expenses (Line 18)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr4", "name": "Shipping & Postage", "keyword": "postage", "category": "shipping_postage", "schedule_line": "[Other Expenses (Line 27a)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr5", "name": "Meals & Entertainment", "keyword": "meal", "category": "meals_entertainment", "schedule_line": "[Meals and Entertainment (Line 24b)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": "50%", "override_allowed": True, "auto_apply": True},
    {"id": "tr6", "name": "Repairs & Maintenance", "keyword": "repair", "category": "repairs_maintenance", "schedule_line": "[Repairs and Maintenance (Line 21)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr7", "name": "Software & SaaS", "keyword": "software", "category": "software_saas", "schedule_line": "[Other Expenses (Line 27a)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr8", "name": "Taxes & Licenses", "keyword": "tax", "category": "taxes_licenses", "schedule_line": "[Taxes and Licenses (Line 23)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr9", "name": "Utilities", "keyword": "utilities", "category": "utilities", "schedule_line": "[Utilities (Line 25)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr10", "name": "Home Office Deduction", "keyword": "home office", "category": "home_office", "schedule_line": "[Home Office (Form 8829)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": False},
    {"id": "tr11", "name": "Health Insurance", "keyword": "health insurance", "category": "health_insurance", "schedule_line": "[Self-Employed Health Insurance (Line 29)]", "deductible": True, "entity_types": ["Individual", "LLC", "S-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": False},
    {"id": "tr12", "name": "Retirement Contribution", "keyword": "retirement", "category": "retirement_contribution", "schedule_line": "[Retirement Plans (Line 28)]", "deductible": True, "entity_types": ["Individual", "LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": False},
    {"id": "tr13", "name": "Contractor Payments", "keyword": "contractor", "category": "contractor_expense", "schedule_line": "[Contract Labor (Line 11)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": "600.00", "max_amount": None, "override_allowed": True, "auto_apply": True},
    {"id": "tr14", "name": "Depreciation", "keyword": "depreciation", "category": "depreciation", "schedule_line": "[Depreciation (Line 13)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "C-Corp", "Partnership"], "threshold": None, "max_amount": None, "override_allowed": True, "auto_apply": False},
    {"id": "tr15", "name": "QBI Deduction", "keyword": "qbi", "category": "qbi_deduction", "schedule_line": "[Qualified Business Income (Form 8995)]", "deductible": True, "entity_types": ["LLC", "S-Corp", "Partnership"], "threshold": None, "max_amount": "20%", "override_allowed": True, "auto_apply": False},
]

router = APIRouter()


def _ensure_rules():
    db = get_db()
    if "tax_rules" not in db:
        db["tax_rules"] = {r["id"]: r for r in DEFAULT_RULES}
        save_db(db)
    return db


@router.get("/", response_model=List[TaxRuleOut])
async def list_rules():
    db = _ensure_rules()
    rules = db.get("tax_rules", {})
    result = []
    for r in rules.values():
        result.append(TaxRuleOut(
            id=r["id"],
            name=r["name"],
            keyword=r["keyword"],
            category=r["category"],
            schedule_line=r["schedule_line"],
            deductible=r["deductible"],
            entity_types=r["entity_types"],
            threshold=r.get("threshold"),
            max_amount=r.get("max_amount"),
            override_allowed=r.get("override_allowed", False),
            auto_apply=r.get("auto_apply", True),
        ))
    return result


@router.get("/{rule_id}", response_model=TaxRuleOut)
async def get_rule(rule_id: str):
    db = _ensure_rules()
    r = db.get("tax_rules", {}).get(rule_id)
    if not r:
        raise HTTPException(404, f"Rule {rule_id} not found")
    return TaxRuleOut(
        id=r["id"],
        name=r["name"],
        keyword=r["keyword"],
        category=r["category"],
        schedule_line=r["schedule_line"],
        deductible=r["deductible"],
        entity_types=r["entity_types"],
        threshold=r.get("threshold"),
        max_amount=r.get("max_amount"),
        override_allowed=r.get("override_allowed", False),
        auto_apply=r.get("auto_apply", True),
    )


@router.patch("/{rule_id}", response_model=TaxRuleOut)
async def update_rule(rule_id: str, update: TaxRuleUpdate):
    db = _ensure_rules()
    r = db.get("tax_rules", {}).get(rule_id)
    if not r:
        raise HTTPException(404, f"Rule {rule_id} not found")

    if update.override_allowed is not None:
        r["override_allowed"] = update.override_allowed
    if update.auto_apply is not None:
        r["auto_apply"] = update.auto_apply
    if update.threshold is not None:
        r["threshold"] = update.threshold
    if update.max_amount is not None:
        r["max_amount"] = update.max_amount

    save_db(db)
    log_event("INFO", "TAX_RULE_UPDATED", f"Updated tax rule: {r['name']}")
    return TaxRuleOut(
        id=r["id"],
        name=r["name"],
        keyword=r["keyword"],
        category=r["category"],
        schedule_line=r["schedule_line"],
        deductible=r["deductible"],
        entity_types=r["entity_types"],
        threshold=r.get("threshold"),
        max_amount=r.get("max_amount"),
        override_allowed=r.get("override_allowed", False),
        auto_apply=r.get("auto_apply", True),
    )
