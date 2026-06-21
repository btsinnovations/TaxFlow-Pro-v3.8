from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..rls import is_postgres, set_tenant_id
from .auth import get_current_user
from ..local.ml_pipeline import train_local_model, load_local_model, predict_local, TrainingError
from ..local import settings as local_settings

CATEGORY_RULES = {
    "SALARY": "Income", "PAYROLL": "Income", "DEPOSIT": "Income", "BAH": "Income",
    "TREAS": "Income", "IRS": "Income", "TAX REFUND": "Income",
    "DIVIDEND": "Investment Income", "INTEREST": "Investment Income",
    "STARBUCKS": "Food & Dining", "COFFEE": "Food & Dining", "RESTAURANT": "Food & Dining",
    "MCDONALDS": "Food & Dining", "SUBWAY": "Food & Dining", "CHIPOTLE": "Food & Dining",
    "DOORDASH": "Food & Dining",
    "WALMART": "Shopping", "TARGET": "Shopping", "AMAZON": "Shopping",
    "BEST BUY": "Shopping", "HOME DEPOT": "Shopping", "LOWES": "Shopping",
    "SHELL": "Auto & Transport", "CHEVRON": "Auto & Transport", "GAS": "Auto & Transport",
    "GEICO": "Auto & Transport", "UBER": "Auto & Transport",
    "NETFLIX": "Entertainment", "SPOTIFY": "Entertainment", "HULU": "Entertainment",
    "STEAM": "Entertainment",
    "ELECTRIC": "Utilities", "INTERNET": "Utilities", "PHONE": "Utilities",
    "GYM": "Health & Fitness", "PHARMACY": "Health & Fitness", "DENTIST": "Health & Fitness",
    "CVS": "Health & Fitness",
    "ZELLE": "Transfer", "VENMO": "Transfer", "ATM": "Cash & ATM",
    "COURTESY PAY": "Fees & Charges", "FEE": "Fees & Charges",
    "INSURANCE": "Insurance", "RENT": "Housing", "MORTGAGE": "Housing",
}

def categorize(description: str) -> str:
    desc_upper = description.upper()
    for keyword, category in CATEGORY_RULES.items():
        if keyword in desc_upper:
            return category
    return "Uncategorized"

router = APIRouter(prefix="/ml", tags=["ml"])

def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass

@router.get("/status")
def ml_status():
    model = load_local_model()
    if model is None:
        return {
            "enabled": False,
            "model_version": None,
            "accuracy": None,
            "last_trained": None,
            "training_samples": None,
            "message": "No local model found. Train one with POST /api/ml/train",
        }
    # Metadata was written at train time; try to load it.
    import json
    from pathlib import Path
    from ..local.settings import LOCAL_ROOT
    meta_path = LOCAL_ROOT / "ml" / "model_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    return {
        "enabled": True,
        "model_version": "local",
        "accuracy": meta.get("accuracy"),
        "last_trained": None,
        "training_samples": meta.get("support"),
        "message": "Local model loaded",
    }

@router.post("/toggle")
def ml_toggle():
    return {
        "enabled": False,
        "message": "ML toggling is not implemented in this version. Train a local model with POST /api/ml/train.",
    }

@router.post("/train")
def train_model(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Train a local model on the current user's labeled transactions."""
    _wrap_tenant(request, db)

    txs = (
        db.query(models.Transaction)
        .join(models.Statement)
        .filter(models.Statement.user_id == current_user.id)
        .filter(models.Transaction.category != None)
        .all()
    )
    transactions = [
        {"description": tx.description, "category": tx.category}
        for tx in txs
    ]
    if len(transactions) < 10:
        raise HTTPException(status_code=400, detail="Need at least 10 labeled transactions to train.")

    try:
        result = train_local_model(transactions)
    except TrainingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "accuracy": result.accuracy,
        "f1_macro": result.f1_macro,
        "support": result.support,
        "classes": result.classes,
        "model_path": str(result.model_path),
    }

@router.get("/model-info")
def model_info():
    import json
    from pathlib import Path
    from ..local.settings import LOCAL_ROOT
    meta_path = LOCAL_ROOT / "ml" / "model_meta.json"
    if not meta_path.exists():
        return {"trained": False}
    return {"trained": True, **json.loads(meta_path.read_text())}

@router.post("/categorize/{statement_id}")
def categorize_statement(request: Request, statement_id: int,
                         db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    statement = db.query(models.Statement).filter(
        models.Statement.id == statement_id,
        models.Statement.user_id == current_user.id
    ).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    transactions = db.query(models.Transaction).filter(
        models.Transaction.statement_id == statement_id,
        models.Transaction.tenant_id == statement.tenant_id
    ).all()

    model = load_local_model()
    updated = 0
    for tx in transactions:
        if model is not None:
            try:
                cat, _ = predict_local(tx.description, model)
            except Exception:
                cat = categorize(tx.description)
        else:
            cat = categorize(tx.description)
        if tx.category != cat:
            tx.category = cat
            updated += 1
    db.commit()

    return {
        "statement_id": statement_id,
        "transactions_processed": len(transactions),
        "categories_updated": updated,
        "categories": list(set(t.category for t in transactions))
    }
