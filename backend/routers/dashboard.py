<<<<<<< HEAD
from fastapi import APIRouter, Depends
=======
from fastapi import APIRouter, Depends, Request
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models
<<<<<<< HEAD
=======
from ..rls import is_postgres, set_tenant_id
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
from .auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

<<<<<<< HEAD
@router.get("/")
def get_dashboard(db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    total_accounts = db.query(models.Account).filter(models.Account.user_id == current_user.id).count()
    total_statements = db.query(models.Statement).filter(models.Statement.user_id == current_user.id).count()
    total_transactions = db.query(models.Transaction).join(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).count()
    total_volume = db.query(func.sum(models.Transaction.amount)).join(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).scalar() or 0.0
=======
def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass

@router.get("/")
def get_dashboard(request: Request,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    total_accounts = db.query(models.Account).filter(models.Account.user_id == current_user.id).count()
    total_statements = db.query(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).count()
    total_transactions = db.query(models.Transaction).join(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).count()
    
    total_volume = db.query(func.sum(models.Transaction.amount)).join(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).scalar() or 0.0
    
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    recent = db.query(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).order_by(models.Statement.created_at.desc()).limit(5).all()
    
    return {
        "total_accounts": total_accounts,
        "total_statements": total_statements,
        "total_transactions": total_transactions,
        "total_volume": round(float(total_volume), 2),
        "recent_statements": [
            {
                "id": s.id, "filename": s.filename, "account_id": s.account_id,
<<<<<<< HEAD
                "is_balanced": s.is_balanced,
                "variance": float(s.variance) if s.variance is not None else None,
=======
                "is_balanced": s.is_balanced, "variance": float(s.variance) if s.variance else None,
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
                "created_at": s.created_at.isoformat() if s.created_at else None
            } for s in recent
        ]
    }
