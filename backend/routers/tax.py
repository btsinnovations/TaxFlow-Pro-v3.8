from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models
from ..rls import is_postgres, set_tenant_id
from .auth import get_current_user

router = APIRouter(prefix="/tax", tags=["tax"])

def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass

@router.get("/summary/{year}")
def tax_summary(request: Request, year: int,
                db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    prefix = f"{year}-"

    income = db.query(func.sum(models.Transaction.amount)).join(models.Statement).filter(
        models.Statement.user_id == current_user.id,
        models.Transaction.amount > 0,
        models.Transaction.date.startswith(prefix)
    ).scalar() or 0.0

    expenses = db.query(func.sum(models.Transaction.amount)).join(models.Statement).filter(
        models.Statement.user_id == current_user.id,
        models.Transaction.amount < 0,
        models.Transaction.date.startswith(prefix)
    ).scalar() or 0.0

    return {
        "year": year,
        "total_income": round(float(income), 2),
        "total_expenses": round(float(abs(expenses)), 2),
        "net": round(float(income + expenses), 2)
    }
