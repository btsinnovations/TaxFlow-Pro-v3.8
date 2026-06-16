"""
Reclassify router: change transaction categories individually or in bulk,
plus list available tax categories.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(tags=["reclassify"])

# Comprehensive tax category list for Schedule C, Schedule E, etc.
TAX_CATEGORIES = [
    {"code": "advertising", "name": "Advertising", "schedule": "C", "line": "8"},
    {"code": "car and truck", "name": "Car and Truck Expenses", "schedule": "C", "line": "9"},
    {"code": "commissions", "name": "Commissions and Fees", "schedule": "C", "line": "10"},
    {"code": "contract labor", "name": "Contract Labor", "schedule": "C", "line": "11"},
    {"code": "depletion", "name": "Depletion", "schedule": "C", "line": "12"},
    {"code": "depreciation", "name": "Depreciation", "schedule": "C", "line": "13"},
    {"code": "section_179", "name": "Section 179 Expense Deduction", "schedule": "C", "line": "13"},
    {"code": "employee benefits", "name": "Employee Benefit Programs", "schedule": "C", "line": "14"},
    {"code": "insurance", "name": "Insurance (Other than Health)", "schedule": "C", "line": "15"},
    {"code": "health insurance", "name": "Health Insurance", "schedule": "SE", "line": ""},
    {"code": "interest_mortgage", "name": "Interest - Mortgage", "schedule": "C", "line": "16a"},
    {"code": "interest_other", "name": "Interest - Other", "schedule": "C", "line": "16b"},
    {"code": "legal", "name": "Legal and Professional Services", "schedule": "C", "line": "17"},
    {"code": "office", "name": "Office Expense", "schedule": "C", "line": "18"},
    {"code": "pension", "name": "Pension and Profit-Sharing Plans", "schedule": "C", "line": "19"},
    {"code": "rent_vehicle", "name": "Rent or Lease - Vehicles/Machinery", "schedule": "C", "line": "20a"},
    {"code": "rent_other", "name": "Rent or Lease - Other Business Property", "schedule": "C", "line": "20b"},
    {"code": "repairs", "name": "Repairs and Maintenance", "schedule": "C", "line": "21"},
    {"code": "supplies", "name": "Supplies", "schedule": "C", "line": "22"},
    {"code": "taxes", "name": "Taxes and Licenses", "schedule": "C", "line": "23"},
    {"code": "travel", "name": "Travel", "schedule": "C", "line": "24a"},
    {"code": "meals", "name": "Meals (50% deductible)", "schedule": "C", "line": "24b"},
    {"code": "utilities", "name": "Utilities", "schedule": "C", "line": "25"},
    {"code": "wages", "name": "Wages", "schedule": "C", "line": "26"},
    {"code": "other", "name": "Other Expenses", "schedule": "C", "line": "27"},
    {"code": "income_sales", "name": "Gross Receipts or Sales", "schedule": "C", "line": "1"},
    {"code": "income_returns", "name": "Returns and Allowances", "schedule": "C", "line": "2"},
    {"code": "income_other", "name": "Other Income", "schedule": "C", "line": "6"},
    {"code": "cost_of_goods", "name": "Cost of Goods Sold", "schedule": "C", "line": "4"},
    {"code": "rental_income", "name": "Rents Received", "schedule": "E", "line": "3"},
    {"code": "royalty_income", "name": "Royalties Received", "schedule": "E", "line": "4"},
    {"code": "rental_expenses", "name": "Rental Expenses", "schedule": "E", "line": ""},
    {"code": "home_office", "name": "Business Use of Home", "schedule": "C", "line": "30"},
    {"code": "charitable_contributions", "name": "Charitable Contributions", "schedule": "A", "line": ""},
    {"code": "education", "name": "Education Expenses", "schedule": "C", "line": "27"},
    {"code": "dues", "name": "Dues and Subscriptions", "schedule": "C", "line": "27"},
    {"code": "freight", "name": "Freight and Shipping", "schedule": "C", "line": "27"},
    {"code": "gifts", "name": "Business Gifts", "schedule": "C", "line": "27"},
    {"code": "telephone", "name": "Telephone and Internet", "schedule": "C", "line": "25"},
    {"code": "uniforms", "name": "Uniforms", "schedule": "C", "line": "27"},
    {"code": "uncategorized", "name": "Uncategorized", "schedule": "", "line": ""},
]


class ReclassifyRequest(BaseModel):
    new_category: str
    reason: Optional[str] = None


class BulkReclassifyRequest(BaseModel):
    transaction_ids: List[int]
    new_category: str
    reason: Optional[str] = None


class ReclassifyResponse(BaseModel):
    transaction_id: int
    old_category: str
    new_category: str
    success: bool


class BulkReclassifyResponse(BaseModel):
    results: List[ReclassifyResponse]
    total_success: int
    total_failed: int


class CategoryResponse(BaseModel):
    code: str
    name: str
    schedule: str
    line: str


@router.post("/transactions/{transaction_id}/reclassify", response_model=ReclassifyResponse)
def reclassify_transaction(
    transaction_id: int,
    req: ReclassifyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Ownership check via statement -> account -> user
    stmt = (
        db.query(models.Statement)
        .filter(models.Statement.id == tx.statement_id)
        .first()
    ) if tx.statement_id else None

    if stmt:
        acct = (
            db.query(models.Account)
            .filter(models.Account.id == stmt.account_id)
            .first()
        )
        if acct and acct.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

    old_category = tx.category or "uncategorized"
    tx.category = req.new_category
    db.commit()

    # Audit trail
    tenant_id = tx.tenant_id or (stmt.tenant_id if stmt else 0)
    audit = models.AuditEntry(
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="reclassify",
        entity_type="transaction",
        entity_id=transaction_id,
        details=f"Reclassified from '{old_category}' to '{req.new_category}'. Reason: {req.reason or 'N/A'}",
    )
    db.add(audit)
    db.commit()

    return ReclassifyResponse(
        transaction_id=transaction_id,
        old_category=old_category,
        new_category=req.new_category,
        success=True,
    )


@router.post("/transactions/bulk-reclassify", response_model=BulkReclassifyResponse)
def bulk_reclassify(
    req: BulkReclassifyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not req.transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")
    if len(req.transaction_ids) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 transactions per bulk operation")

    results = []
    success_count = 0
    failed_count = 0

    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.id.in_(req.transaction_ids))
        .all()
    )

    tx_map = {tx.id: tx for tx in transactions}

    for tx_id in req.transaction_ids:
        tx = tx_map.get(tx_id)
        if not tx:
            results.append(ReclassifyResponse(
                transaction_id=tx_id,
                old_category="",
                new_category=req.new_category,
                success=False,
            ))
            failed_count += 1
            continue

        old_category = tx.category or "uncategorized"
        tx.category = req.new_category

        results.append(ReclassifyResponse(
            transaction_id=tx_id,
            old_category=old_category,
            new_category=req.new_category,
            success=True,
        ))
        success_count += 1

    db.commit()

    if success_count > 0:
        audit = models.AuditEntry(
            tenant_id=transactions[0].tenant_id if transactions else 0,
            user_id=current_user.id,
            action="bulk_reclassify",
            entity_type="transaction",
            entity_id=0,
            details=f"Bulk reclassified {success_count} transactions to '{req.new_category}'",
        )
        db.add(audit)
        db.commit()

    return BulkReclassifyResponse(
        results=results,
        total_success=success_count,
        total_failed=failed_count,
    )


@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(
    schedule: Optional[str] = Query(None, description="Filter by schedule (C, E, A, SE)"),
    current_user: models.User = Depends(get_current_user),
):
    cats = TAX_CATEGORIES
    if schedule:
        cats = [c for c in cats if c["schedule"].upper() == schedule.upper()]
    return [CategoryResponse(**c) for c in cats]
