"""Transaction builder utilities for backend/parsers."""
from decimal import Decimal
from typing import Any, Dict, List
from backend.models import Transaction as DBTransaction  # for type hints only


def ensure_tx_type(amount: Any) -> str:
    """Return credit/debit based on numeric sign."""
    try:
        return "credit" if Decimal(str(amount)) > 0 else "debit"
    except Exception:
        return "debit"


def dict_to_backend_model(tx_dict: Dict[str, Any], statement_id: int, tenant_id: int, user_id: int) -> Dict[str, Any]:
    """Convert a unified parser dict to backend DB insert kwargs."""
    amount = tx_dict.get("amount")
    date_val = tx_dict.get("date")
    from datetime import date as _date
    if isinstance(date_val, str) and date_val:
        try:
            date_val = _date.fromisoformat(date_val)
        except ValueError:
            date_val = None
    return {
        "statement_id": statement_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "date": date_val,
        "description": tx_dict.get("description", "")[:255],
        "amount": Decimal(str(amount)) if amount is not None else Decimal("0.00"),
        "tx_type": ensure_tx_type(amount),
        "category": tx_dict.get("category") or "uncategorized",
        "running_balance": Decimal(str(tx_dict["balance"])) if tx_dict.get("balance") is not None else None,
    }


def model_to_dict(tx_model: Any) -> Dict[str, Any]:
    """Convert a SQLAlchemy Transaction row to API-compatible dict."""
    date_val = tx_model.date
    if isinstance(date_val, DBTransaction.__table__.c.date.type.python_type):
        date_val = date_val.isoformat()
    return {
        "id": tx_model.id,
        "statement_id": tx_model.statement_id,
        "tenant_id": tx_model.tenant_id,
        "date": date_val,
        "description": tx_model.description,
        "amount": float(tx_model.amount) if tx_model.amount is not None else None,
        "tx_type": tx_model.tx_type,
        "category": tx_model.category,
        "running_balance": float(tx_model.running_balance) if tx_model.running_balance is not None else None,
        "created_at": tx_model.created_at.isoformat() if tx_model.created_at else None,
    }


def deduplicate_dicts(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate dict transactions by stable key (date, description, amount)."""
    seen = set()
    unique = []
    for tx in transactions:
        key = (
            tx.get("date") or "",
            (tx.get("description") or "").strip().upper(),
            f"{Decimal(str(tx.get('amount') or 0)):.2f}",
        )
        if key not in seen:
            seen.add(key)
            unique.append(tx)
    return unique
