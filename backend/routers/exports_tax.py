"""
Tax software export router: Drake, Lacerte, ProConnect (TXF) formats.
Produces downloadable CSV/TXF with Content-Disposition headers.
"""
import csv
import io
import os
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models
from .auth import get_current_user

router = APIRouter(prefix="/exports", tags=["exports_tax"])

# Category-to-Drake-line mapping (simplified Schedule C mapping)
CATEGORY_TO_DRAKE = {
    "advertising": ("Schedule C", "Line 8", "Advertising"),
    "car and truck": ("Schedule C", "Line 9", "Car and truck expenses"),
    "commissions": ("Schedule C", "Line 10", "Commissions and fees"),
    "contract labor": ("Schedule C", "Line 11", "Contract labor"),
    "depletion": ("Schedule C", "Line 12", "Depletion"),
    "depreciation": ("Schedule C", "Line 13", "Depreciation and section 179"),
    "employee benefits": ("Schedule C", "Line 14", "Employee benefit programs"),
    "insurance": ("Schedule C", "Line 15", "Insurance (other than health)"),
    "interest": ("Schedule C", "Line 16", "Interest"),
    "mortgage": ("Schedule C", "Line 16a", "Mortgage interest"),
    "legal": ("Schedule C", "Line 17", "Legal and professional services"),
    "office": ("Schedule C", "Line 18", "Office expense"),
    "pension": ("Schedule C", "Line 19", "Pension and profit-sharing plans"),
    "rent": ("Schedule C", "Line 20a", "Rent or lease - Vehicles, machinery"),
    "repairs": ("Schedule C", "Line 21", "Repairs and maintenance"),
    "supplies": ("Schedule C", "Line 22", "Supplies"),
    "taxes": ("Schedule C", "Line 23", "Taxes and licenses"),
    "travel": ("Schedule C", "Line 24a", "Travel"),
    "meals": ("Schedule C", "Line 24b", "Meals"),
    "utilities": ("Schedule C", "Line 25", "Utilities"),
    "wages": ("Schedule C", "Line 26", "Wages"),
    "other": ("Schedule C", "Line 27", "Other expenses"),
}

# Category-to-Lacerte mapping
CATEGORY_TO_LACERTE = {
    "advertising": ("SCHC", "8", "Advertising"),
    "car and truck": ("SCHC", "9", "Car and truck expenses"),
    "commissions": ("SCHC", "10", "Commissions and fees"),
    "contract labor": ("SCHC", "11", "Contract labor"),
    "depletion": ("SCHC", "12", "Depletion"),
    "depreciation": ("SCHC", "13", "Depreciation"),
    "employee benefits": ("SCHC", "14", "Employee benefit programs"),
    "insurance": ("SCHC", "15", "Insurance"),
    "interest": ("SCHC", "16", "Interest"),
    "legal": ("SCHC", "17", "Legal and professional services"),
    "office": ("SCHC", "18", "Office expense"),
    "pension": ("SCHC", "19", "Pension and profit-sharing"),
    "rent": ("SCHC", "20a", "Rent or lease"),
    "repairs": ("SCHC", "21", "Repairs and maintenance"),
    "supplies": ("SCHC", "22", "Supplies"),
    "taxes": ("SCHC", "23", "Taxes and licenses"),
    "travel": ("SCHC", "24a", "Travel"),
    "meals": ("SCHC", "24b", "Meals"),
    "utilities": ("SCHC", "25", "Utilities"),
    "wages": ("SCHC", "26", "Wages"),
    "other": ("SCHC", "27", "Other expenses"),
}


def _map_to_drake(category: str):
    cat_lower = (category or "uncategorized").lower()
    return CATEGORY_TO_DRAKE.get(cat_lower, ("Schedule C", "Line 27", f"Other - {category}"))


def _map_to_lacerte(category: str):
    cat_lower = (category or "uncategorized").lower()
    return CATEGORY_TO_LACERTE.get(cat_lower, ("SCHC", "27", f"Other - {category}"))


def _build_drake_csv(transactions: list) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Form", "Line", "Description", "Amount"])
    for tx in transactions:
        form, line, desc = _map_to_drake(tx.category)
        amount = float(tx.amount) if tx.amount else 0.0
        if tx.tx_type == "credit":
            amount = -amount
        writer.writerow([form, line, tx.description or desc, f"{amount:.2f}"])
    return output.getvalue()


def _build_lacerte_csv(transactions: list) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ExportID", "Form", "Line#", "Description", "Amount"])
    for idx, tx in enumerate(transactions, 1):
        form, line, desc = _map_to_lacerte(tx.category)
        amount = float(tx.amount) if tx.amount else 0.0
        if tx.tx_type == "credit":
            amount = -amount
        writer.writerow([f"EXP{idx:05d}", form, line, tx.description or desc, f"{amount:.2f}"])
    return output.getvalue()


def _build_txf(transactions: list) -> str:
    lines = ["^", "ACCTINFO", "^"]
    for tx in transactions:
        amount = float(tx.amount) if tx.amount else 0.0
        if tx.tx_type == "credit":
            amount = -amount
        date_val = (tx.date or "").replace("-", "")
        cat = (tx.category or "uncategorized").upper().replace(" ", "_")
        lines.append("^")
        lines.append("TRNS")
        lines.append(f"D{date_val}")
        lines.append(f"T{amount:.2f}")
        lines.append(f"M{tx.description or ''}")
        lines.append(f"N{cat}")
        lines.append("^")
    lines.append("^")
    lines.append("ENDACCTINFO")
    lines.append("^")
    return "\n".join(lines)


@router.get("/tax-software")
def export_tax_software(
    format: Literal["drake", "lacerte", "proconnect"] = Query(..., description="Export format"),
    client_id: int = Query(..., description="Client ID"),
    year: int = Query(..., description="Tax year"),
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

    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"

    transactions = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.client_id == client_id,
            models.Transaction.date >= year_start,
            models.Transaction.date <= year_end,
            models.Transaction.archived == False,
        )
        .order_by(models.Transaction.date)
        .all()
    )

    if not transactions:
        raise HTTPException(
            status_code=404, detail="No transactions found for this client/year"
        )

    filename_base = f"tax_export_client{client_id}_{year}"

    if format == "drake":
        content = _build_drake_csv(transactions)
        filename = f"{filename_base}_drake.csv"
        media_type = "text/csv"
    elif format == "lacerte":
        content = _build_lacerte_csv(transactions)
        filename = f"{filename_base}_lacerte.csv"
        media_type = "text/csv"
    elif format == "proconnect":
        content = _build_txf(transactions)
        filename = f"{filename_base}.txf"
        media_type = "application/octet-stream"
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
