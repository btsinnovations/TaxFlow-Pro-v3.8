"""
Transaction list/query router for TaxFlow Pro v3.8.

Provides paginated transaction listing with multi-column filtering,
summary aggregation, soft-delete (archive), and field-level patching.
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id
from ..audit.audit_trail import (
    create_audit_entry,
    ACTION_UPDATE_TRANSACTION,
    ACTION_DELETE_TRANSACTION,
)
from .auth import get_current_user

router = APIRouter(tags=["transactions-list"])


def _wrap_tenant(request: Request, db: Session) -> None:
    """Set RLS tenant context when X-Tenant-ID header is present on PostgreSQL."""
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass


def _get_tenant_id(request: Request, client_id: int) -> int:
    """Resolve tenant_id from request state or fall back to client_id."""
    tenant_id = getattr(request.state, "tenant_id", None)
    return tenant_id if tenant_id is not None else client_id


# ---------------------------------------------------------------------------
# List / Query
# ---------------------------------------------------------------------------

@router.get("/transactions", response_model=List[schemas.Transaction])
def list_transactions(
    request: Request,
    client_id: int,
    year: Optional[str] = None,
    category: Optional[str] = None,
    confirmed: Optional[bool] = None,
    archived: Optional[bool] = False,
    search: Optional[str] = None,
    tx_type: Optional[str] = None,
    is_manual: Optional[bool] = None,
    is_journal: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    order_by: str = "date",
    order_dir: str = "desc",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Query transactions with flexible filters and ordering.

    Query params:
        * client_id  - Required. Filters by tenant_id.
        * year       - Filter by transaction year (date prefix).
        * category   - Exact category match.
        * confirmed  - Filter by confirmation status.
        * archived   - Include archived transactions (default: false).
        * search     - Free-text search on description.
        * tx_type    - Filter by 'debit' or 'credit'.
        * is_manual  - Filter manual transactions.
        * is_journal - Filter journal-entry transactions.
        * order_by   - Column to sort by: 'date', 'amount', 'category', 'created_at'.
        * order_dir  - 'asc' or 'desc'.
    """
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    query = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
    )

    # Year filter
    if year:
        query = query.filter(
            models.Transaction.date >= f"{year}-01-01",
            models.Transaction.date <= f"{year}-12-31",
        )

    # Category filter
    if category:
        query = query.filter(models.Transaction.category == category)

    # Confirmed filter
    if confirmed is not None:
        query = query.filter(models.Transaction.confirmed == confirmed)

    # Archived filter
    if archived is not None:
        query = query.filter(models.Transaction.archived == archived)

    # Transaction type filter
    if tx_type:
        query = query.filter(models.Transaction.tx_type == tx_type)

    # Manual filter
    if is_manual is not None:
        query = query.filter(models.Transaction.is_manual == is_manual)

    # Journal filter
    if is_journal is not None:
        query = query.filter(models.Transaction.is_journal == is_journal)

    # Free-text search on description
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Transaction.description.ilike(like_pattern),
                models.Transaction.category.ilike(like_pattern),
            )
        )

    # Ordering
    order_column_map = {
        "date": models.Transaction.date,
        "amount": models.Transaction.amount,
        "category": models.Transaction.category,
        "created_at": models.Transaction.created_at,
        "id": models.Transaction.id,
    }
    order_col = order_column_map.get(order_by, models.Transaction.date)
    if order_dir.lower() == "asc":
        query = query.order_by(asc(order_col))
    else:
        query = query.order_by(desc(order_col))

    return query.offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# Update (PATCH)
# ---------------------------------------------------------------------------

class TransactionUpdateRequest(schemas.TransactionBase):
    """Partial update schema - all fields optional."""
    model_config = {"from_attributes": True}

    date: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    tx_type: Optional[str] = None
    category: Optional[str] = None
    confirmed: Optional[bool] = None
    tax_line: Optional[str] = None
    running_balance: Optional[float] = None


@router.patch("/transactions/{tx_id}", response_model=schemas.Transaction)
def update_transaction(
    request: Request,
    tx_id: int,
    update_data: TransactionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Update specific fields on a transaction.
    Only provided fields are modified (partial update).
    """
    _wrap_tenant(request, db)
    tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == tx_id)
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    # Capture old values for audit
    old_values = {}
    update_dict = update_data.model_dump(exclude_unset=True)

    # Remove base fields that weren't actually provided
    for key, value in update_dict.items():
        if hasattr(tx, key):
            old_values[key] = getattr(tx, key)
            setattr(tx, key, value)

    if not old_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    db.commit()
    db.refresh(tx)

    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_UPDATE_TRANSACTION,
        entity_type="Transaction",
        entity_id=tx.id,
        old_values=old_values,
        new_values=update_dict,
        client_id=tx.tenant_id,
    )
    db.commit()

    return tx


# ---------------------------------------------------------------------------
# Soft delete (archive)
# ---------------------------------------------------------------------------

@router.delete("/transactions/{tx_id}")
def archive_transaction(
    request: Request,
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Soft-delete a transaction by setting archived=True.
    Hard delete is intentionally not exposed.
    """
    _wrap_tenant(request, db)
    tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == tx_id)
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    if tx.archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction is already archived.",
        )

    old_values = {"archived": tx.archived}
    tx.archived = True
    db.commit()
    db.refresh(tx)

    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_DELETE_TRANSACTION,
        entity_type="Transaction",
        entity_id=tx.id,
        old_values=old_values,
        new_values={"archived": True},
        client_id=tx.tenant_id,
    )
    db.commit()

    return {"ok": True, "transaction_id": tx_id, "archived": True}


# ---------------------------------------------------------------------------
# Summary aggregation
# ---------------------------------------------------------------------------

@router.get("/transactions/summary")
def transactions_summary(
    request: Request,
    client_id: int,
    year: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Aggregate statistics for transactions matching the filters.

    Returns counts, sums by type, category breakdown, and
    confirmation status summary.
    """
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    query = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.archived == False,
    )

    if year:
        query = query.filter(
            models.Transaction.date >= f"{year}-01-01",
            models.Transaction.date <= f"{year}-12-31",
        )

    if category:
        query = query.filter(models.Transaction.category == category)

    # Total count
    total_count = query.with_entities(func.count(models.Transaction.id)).scalar() or 0

    # Sum by tx_type
    debit_sum = (
        query.with_entities(func.coalesce(func.sum(models.Transaction.amount), 0))
        .filter(models.Transaction.tx_type == "debit")
        .scalar()
    ) or 0

    credit_sum = (
        query.with_entities(func.coalesce(func.sum(models.Transaction.amount), 0))
        .filter(models.Transaction.tx_type == "credit")
        .scalar()
    ) or 0

    # Confirmed vs unconfirmed
    confirmed_count = (
        query.with_entities(func.count(models.Transaction.id))
        .filter(models.Transaction.confirmed == True)
        .scalar()
    ) or 0

    unconfirmed_count = (
        query.with_entities(func.count(models.Transaction.id))
        .filter(models.Transaction.confirmed == False)
        .scalar()
    ) or 0

    # Category breakdown
    category_rows = (
        query.with_entities(
            models.Transaction.category,
            func.count(models.Transaction.id).label("count"),
            func.coalesce(func.sum(models.Transaction.amount), 0).label("total"),
        )
        .group_by(models.Transaction.category)
        .all()
    )

    categories = []
    for cat, count, total in category_rows:
        categories.append({
            "category": cat or "uncategorized",
            "count": count,
            "total": float(total) if total else 0.0,
        })

    # Monthly breakdown (group by date prefix YYYY-MM)
    monthly_rows = (
        query.with_entities(
            func.substr(models.Transaction.date, 1, 7).label("month"),
            func.count(models.Transaction.id).label("count"),
            func.coalesce(func.sum(models.Transaction.amount), 0).label("total"),
        )
        .group_by(func.substr(models.Transaction.date, 1, 7))
        .order_by(func.substr(models.Transaction.date, 1, 7))
        .all()
    )

    monthly = []
    for month, count, total in monthly_rows:
        if month:
            monthly.append({
                "month": month,
                "count": count,
                "total": float(total) if total else 0.0,
            })

    return {
        "filters": {
            "client_id": client_id,
            "year": year,
            "category": category,
        },
        "total_count": total_count,
        "debit_total": float(debit_sum),
        "credit_total": float(credit_sum),
        "net_total": float(Decimal(str(debit_sum)) - Decimal(str(credit_sum))),
        "confirmed_count": confirmed_count,
        "unconfirmed_count": unconfirmed_count,
        "categories": categories,
        "monthly": monthly,
    }
