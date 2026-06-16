<<<<<<< HEAD
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
=======
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..rls import is_postgres, set_tenant_id
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
from .auth import get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])

<<<<<<< HEAD
@router.get("/logs")
def get_logs(skip: int = 0, limit: int = 100,
             db: Session = Depends(get_db),
             current_user: models.User = Depends(get_current_user)):
    statements = db.query(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).order_by(models.Statement.created_at.desc()).offset(skip).limit(limit).all()
    
=======
def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass

@router.get("/logs")
def get_logs(request: Request, skip: int = 0, limit: int = 100,
             db: Session = Depends(get_db),
             current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    statements = db.query(models.Statement).filter(
        models.Statement.user_id == current_user.id
    ).order_by(models.Statement.created_at.desc()).offset(skip).limit(limit).all()

>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    return {
        "events": [
            {
                "type": "statement_upload",
                "statement_id": s.id,
                "filename": s.filename,
                "account_id": s.account_id,
                "is_balanced": s.is_balanced,
<<<<<<< HEAD
                "variance": float(s.variance) if s.variance is not None else None,
=======
                "variance": float(s.variance) if s.variance else None,
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
                "created_at": s.created_at.isoformat() if s.created_at else None
            } for s in statements
        ]
    }
