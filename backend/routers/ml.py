from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .auth import get_current_user

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

@router.post("/categorize/{statement_id}")
def categorize_statement(statement_id: int,
                         db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    transactions = db.query(models.Transaction).join(models.Statement).join(models.Account).filter(
        models.Account.user_id == current_user.id,
        models.Transaction.statement_id == statement_id
    ).all()
    
    updated = 0
    for tx in transactions:
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
