import os
import shutil
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .auth import get_current_user
from ..parsers.generic_pdf import GenericPDFParser

router = APIRouter(prefix="/upload", tags=["upload"])
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def to_decimal(value):
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(',', '').replace('$', '').strip()
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        return None

def standardize_date(date_str: str) -> str:
    if not date_str:
        return date_str
    date_str = date_str.strip()
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def clean_header_bleed(desc: str) -> str:
    """Truncate description at the first sign of bank header/footer bleed."""
    if not desc: return desc
    fragments = [
        "Navy Federal", "P.O. Box", "Credit Union", "Statement of Account",
        "Account Summary", "Account Number:", "Statement Period:",
        "JPMorgan Chase", "Chase Total Checking", "Chase Bank",
        "Date      Description", "Withdrawal      Deposit"
    ]
    for frag in fragments:
        idx = desc.find(frag)
        if idx != -1:
            return desc[:idx].strip()
    return desc.strip()

@router.post("/")
async def upload_statement(file: UploadFile = File(...),
                           account_id: Optional[int] = None,
                           db: Session = Depends(get_db),
                           current_user: models.User = Depends(get_current_user)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    safe_name = f"{current_user.id}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        parser = GenericPDFParser(file_path)
        result = parser.parse()
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        elif hasattr(result, "dict"):
            result = result.dict()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parse error: {str(e)}")
    
    stmt_data = result.get("reconciliation", {})
    meta = result.get("meta", {})
    
    statement = models.Statement(
        account_id=account_id,
        user_id=current_user.id,
        filename=file.filename,
        period_start=standardize_date(meta.get("period_start")),
        period_end=standardize_date(meta.get("period_end")),
        opening_balance=to_decimal(stmt_data.get("opening_balance")),
        closing_balance=to_decimal(stmt_data.get("closing_balance")),
        variance=to_decimal(stmt_data.get("variance")),
        is_balanced=stmt_data.get("balanced")
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)
    
    for tx in result.get("transactions", []):
        # --- ROUTER-LEVEL CLEANING: Scrub header bleed before DB insert ---
        tx["description"] = clean_header_bleed(tx.get("description", ""))
        amount_dec = to_decimal(tx.get("amount"))
        tx_type = "credit" if amount_dec and amount_dec > 0 else "debit"
        db_tx = models.Transaction(
            statement_id=statement.id,
            date=standardize_date(tx.get("date")),
            description=tx.get("description"),
            amount=amount_dec,
            tx_type=tx_type,
            running_balance=to_decimal(tx.get("running_balance"))
        )
        db.add(db_tx)
    db.commit()
    
    return {
        "statement_id": statement.id,
        "transactions_count": len(result.get("transactions", [])),
        "variance": float(statement.variance) if statement.variance is not None else None,
        "balanced": statement.is_balanced,
        "template": result.get("template")
    }
