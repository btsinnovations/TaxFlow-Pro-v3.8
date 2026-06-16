"""
Receipt router: upload, list, detail, delete, and match receipts to transactions.
- Confidence scoring weighted: amount 50%, date 30%, description 20%
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(prefix="/receipts", tags=["receipts"])

RECEIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "receipts")


def _ensure_dir():
    os.makedirs(RECEIPTS_DIR, exist_ok=True)


class ReceiptDetail(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    transaction_id: Optional[int] = None
    filename: str
    file_path: str
    ocr_text: Optional[str] = None
    vendor: Optional[str] = None
    amount: Optional[float] = None
    receipt_date: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReceiptMatchResult(BaseModel):
    transaction_id: int
    confidence: float
    factors: dict


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=ReceiptDetail)
async def upload_receipt(
    client_id: int = Form(..., description="Client ID (tenant)"),
    file: UploadFile = File(..., description="Receipt image or PDF"),
    transaction_id: Optional[int] = Form(None),
    vendor: Optional[str] = Form(None),
    amount: Optional[float] = Form(None),
    receipt_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    _ensure_dir()

    original_ext = os.path.splitext(file.filename or "receipt.bin")[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".tiff", ".bmp", ".webp"}
    if original_ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {original_ext}. Allowed: {', '.join(allowed)}",
        )

    unique_name = f"{uuid.uuid4().hex}{original_ext}"
    file_path = os.path.join(RECEIPTS_DIR, unique_name)

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save receipt: {str(exc)}",
        )

    db_receipt = models.Receipt(
        tenant_id=client_id,
        user_id=current_user.id,
        transaction_id=transaction_id,
        filename=file.filename or unique_name,
        file_path=file_path,
        vendor=vendor,
        amount=amount,
        receipt_date=receipt_date,
    )
    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="receipt_upload",
        entity_type="receipt",
        entity_id=db_receipt.id,
        details=f"Uploaded receipt {file.filename}",
    )
    db.add(audit)
    db.commit()

    return ReceiptDetail(
        id=db_receipt.id,
        tenant_id=db_receipt.tenant_id,
        user_id=db_receipt.user_id,
        transaction_id=db_receipt.transaction_id,
        filename=db_receipt.filename,
        file_path=db_receipt.file_path,
        ocr_text=db_receipt.ocr_text,
        vendor=db_receipt.vendor,
        amount=float(db_receipt.amount) if db_receipt.amount else None,
        receipt_date=db_receipt.receipt_date,
        created_at=db_receipt.created_at,
    )


@router.get("", response_model=List[ReceiptDetail])
def list_receipts(
    client_id: int = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client or client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    receipts = (
        db.query(models.Receipt)
        .filter(models.Receipt.tenant_id == client_id)
        .order_by(models.Receipt.created_at.desc())
        .all()
    )
    return [
        ReceiptDetail(
            id=r.id,
            tenant_id=r.tenant_id,
            user_id=r.user_id,
            transaction_id=r.transaction_id,
            filename=r.filename,
            file_path=r.file_path,
            ocr_text=r.ocr_text,
            vendor=r.vendor,
            amount=float(r.amount) if r.amount else None,
            receipt_date=r.receipt_date,
            created_at=r.created_at,
        )
        for r in receipts
    ]


@router.get("/{receipt_id}", response_model=ReceiptDetail)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    receipt = (
        db.query(models.Receipt)
        .filter(models.Receipt.id == receipt_id)
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ReceiptDetail(
        id=receipt.id,
        tenant_id=receipt.tenant_id,
        user_id=receipt.user_id,
        transaction_id=receipt.transaction_id,
        filename=receipt.filename,
        file_path=receipt.file_path,
        ocr_text=receipt.ocr_text,
        vendor=receipt.vendor,
        amount=float(receipt.amount) if receipt.amount else None,
        receipt_date=receipt.receipt_date,
        created_at=receipt.created_at,
    )


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    receipt = (
        db.query(models.Receipt)
        .filter(models.Receipt.id == receipt_id)
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete file from disk
    try:
        if os.path.exists(receipt.file_path):
            os.remove(receipt.file_path)
    except OSError:
        pass

    db.delete(receipt)
    db.commit()
    return None


@router.post("/{receipt_id}/match", response_model=List[ReceiptMatchResult])
def match_receipt(
    receipt_id: int,
    client_id: int = Query(..., description="Client ID for transaction scope"),
    top_n: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    receipt = (
        db.query(models.Receipt)
        .filter(models.Receipt.id == receipt_id)
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get candidate transactions for the client (unmatched, non-archived)
    candidates = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.client_id == client_id,
            models.Transaction.archived == False,
        )
        .order_by(models.Transaction.date.desc())
        .limit(200)
        .all()
    )

    if not candidates:
        return []

    results = []
    receipt_amount = float(receipt.amount) if receipt.amount else None
    receipt_date_str = receipt.receipt_date

    for tx in candidates:
        score = 0.0
        factors = {}

        # Amount match: 50% weight
        if receipt_amount is not None and tx.amount is not None:
            tx_amt = abs(float(tx.amount))
            if tx_amt > 0:
                ratio = min(receipt_amount, tx_amt) / max(receipt_amount, tx_amt)
                amount_score = ratio * 50.0
            elif receipt_amount == 0 and tx_amt == 0:
                amount_score = 50.0
            else:
                amount_score = 0.0
        else:
            amount_score = 0.0
        score += amount_score
        factors["amount"] = round(amount_score, 2)

        # Date match: 30% weight
        if receipt_date_str and tx.date:
            try:
                rdate = datetime.strptime(receipt_date_str, "%Y-%m-%d").date()
                tdate = datetime.strptime(tx.date, "%Y-%m-%d").date()
                delta = abs((rdate - tdate).days)
                if delta == 0:
                    date_score = 30.0
                elif delta <= 1:
                    date_score = 25.0
                elif delta <= 3:
                    date_score = 20.0
                elif delta <= 7:
                    date_score = 15.0
                elif delta <= 14:
                    date_score = 10.0
                elif delta <= 30:
                    date_score = 5.0
                else:
                    date_score = 0.0
            except ValueError:
                date_score = 0.0
        else:
            date_score = 0.0
        score += date_score
        factors["date"] = round(date_score, 2)

        # Description match: 20% weight
        if receipt.ocr_text and tx.description:
            rtext = (receipt.ocr_text or "").lower().split()
            ttext = (tx.description or "").lower().split()
            common = set(rtext) & set(ttext)
            if len(common) > 0:
                desc_score = min(len(common) * 5.0, 20.0)
            else:
                desc_score = 0.0
        elif receipt.vendor and tx.description:
            v_lower = receipt.vendor.lower()
            d_lower = tx.description.lower()
            if v_lower in d_lower or d_lower in v_lower:
                desc_score = 15.0
            else:
                desc_score = 0.0
        else:
            desc_score = 0.0
        score += desc_score
        factors["description"] = round(desc_score, 2)

        results.append(
            ReceiptMatchResult(
                transaction_id=tx.id,
                confidence=round(score, 2),
                factors=factors,
            )
        )

    results.sort(key=lambda x: x.confidence, reverse=True)
    return results[:top_n]
