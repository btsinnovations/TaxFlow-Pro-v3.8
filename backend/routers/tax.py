from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models
from .auth import get_current_user

router = APIRouter(prefix="/tax", tags=["tax"])

@router.get("/summary/{year}")
def tax_summary(year: int,
                db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    prefix = f"{year}-"
    
    income = db.query(func.sum(models.Transaction.amount)).join(models.Statement).join(models.Account).filter(
        models.Account.user_id == current_user.id,
        models.Transaction.amount > 0,
        models.Transaction.date.startswith(prefix)
    ).scalar() or 0.0
    
    expenses = db.query(func.sum(models.Transaction.amount)).join(models.Statement).join(models.Account).filter(
        models.Account.user_id == current_user.id,
        models.Transaction.amount < 0,
        models.Transaction.date.startswith(prefix)
    ).scalar() or 0.0
    
    return {
        "year": year,
        "total_income": round(float(income), 2),
        "total_expenses": round(float(abs(expenses)), 2),
        "net": round(float(income + expenses), 2)
    }
