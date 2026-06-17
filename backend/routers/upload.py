import csv
import io
import os
import shutil
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..parsers.generic_pdf import GenericPDFParser
from ..rls import is_postgres, set_tenant_id
from .auth import get_current_user

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
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def clean_header_bleed(desc: str) -> str:
    """Truncate description at the first sign of bank header/footer bleed."""
    if not desc:
        return desc
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


def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass


def _resolve_account(
    db: Session,
    current_user: models.User,
    account_id: Optional[int],
    client_id: Optional[int],
) -> models.Account:
    """Return a usable account, creating a default client/account if necessary."""
    if account_id is not None:
        account = (
            db.query(models.Account)
            .filter(models.Account.id == account_id, models.Account.user_id == current_user.id)
            .first()
        )
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return account

    if client_id is not None:
        client = (
            db.query(models.Client)
            .filter(models.Client.id == client_id, models.Client.user_id == current_user.id)
            .first()
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        account = (
            db.query(models.Account)
            .filter(models.Account.client_id == client.id, models.Account.user_id == current_user.id)
            .first()
        )
        if not account:
            account = models.Account(
                client_id=client.id,
                tenant_id=client.id,
                user_id=current_user.id,
                name="Primary Checking",
                institution="Unknown",
                type="checking",
            )
            db.add(account)
            db.commit()
            db.refresh(account)
        return account

    # No client/account specified: create a private default client/account for the user.
    default_client = (
        db.query(models.Client)
        .filter(models.Client.user_id == current_user.id, models.Client.name == "Default Client")
        .first()
    )
    if not default_client:
        default_client = models.Client(
            user_id=current_user.id,
            name="Default Client",
        )
        db.add(default_client)
        db.commit()
        db.refresh(default_client)

    account = (
        db.query(models.Account)
        .filter(models.Account.client_id == default_client.id, models.Account.user_id == current_user.id)
        .first()
    )
    if not account:
        account = models.Account(
            client_id=default_client.id,
            tenant_id=default_client.id,
            user_id=current_user.id,
            name="Default Account",
            institution="Unknown",
            type="checking",
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    return account


@router.post("/")
async def upload_statement(
    request: Request,
    file: UploadFile = File(...),
    account_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db)
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    account = _resolve_account(db, current_user, account_id, client_id)

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
        account_id=account.id,
        tenant_id=account.tenant_id,
        user_id=current_user.id,
        filename=file.filename,
        period_start=standardize_date(meta.get("period_start")),
        period_end=standardize_date(meta.get("period_end")),
        opening_balance=to_decimal(stmt_data.get("opening_balance")),
        closing_balance=to_decimal(stmt_data.get("closing_balance")),
        variance=to_decimal(stmt_data.get("variance")),
        is_balanced=stmt_data.get("balanced"),
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)

    for tx in result.get("transactions", []):
        tx["description"] = clean_header_bleed(tx.get("description", ""))
        amount_dec = to_decimal(tx.get("amount"))
        tx_type = "credit" if amount_dec and amount_dec > 0 else "debit"
        db_tx = models.Transaction(
            statement_id=statement.id,
            tenant_id=statement.tenant_id,
            date=standardize_date(tx.get("date")),
            description=tx.get("description"),
            amount=amount_dec,
            tx_type=tx_type,
            running_balance=to_decimal(tx.get("running_balance")),
        )
        db.add(db_tx)
    db.commit()

    return {
        "file_id": statement.id,
        "statement_id": statement.id,
        "account_id": account.id,
        "client_id": account.client_id,
        "transactions_count": len(result.get("transactions", [])),
        "variance": float(statement.variance) if statement.variance is not None else None,
        "balanced": statement.is_balanced,
        "template": result.get("template"),
    }


class _ProcessPayload(BaseModel):
    file_id: int
    output_format: str = "qif"
    # Accepted for frontend compatibility but not required for processing.
    client_id: str = "default"
    profile: str = "personal"
    use_fast: bool = False
    use_ml: bool = True


@router.post("/process")
def process_statement(
    request: Request,
    payload: _ProcessPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return a processing summary for an uploaded statement."""
    _wrap_tenant(request, db)
    statement = (
        db.query(models.Statement)
        .filter(models.Statement.id == payload.file_id, models.Statement.user_id == current_user.id)
        .first()
    )
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    transactions = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.statement_id == statement.id,
            models.Transaction.tenant_id == statement.tenant_id,
        )
        .all()
    )

    warnings = []
    if not statement.is_balanced:
        warnings.append(f"Statement is unbalanced (variance: {statement.variance})")

    reconciliation_status = "PASS" if statement.is_balanced else "FAIL"

    return {
        "success": True,
        "file_id": statement.id,
        "statement_id": statement.id,
        "transaction_count": len(transactions),
        "institution": statement.account.institution if statement.account else "Unknown",
        "reconciliation": {"status": reconciliation_status, "variance": float(statement.variance) if statement.variance is not None else None},
        "output_file": str(statement.id),
        "output_format": payload.output_format,
        "warnings": warnings,
    }


@router.get("/download/{file_id}")
def download_statement(
    request: Request,
    file_id: int,
    format: str = "qif",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Download a processed statement in the requested format."""
    _wrap_tenant(request, db)
    statement = (
        db.query(models.Statement)
        .filter(models.Statement.id == file_id, models.Statement.user_id == current_user.id)
        .first()
    )
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    transactions = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.statement_id == statement.id,
            models.Transaction.tenant_id == statement.tenant_id,
        )
        .order_by(models.Transaction.date.asc())
        .all()
    )

    if format == "json":
        data = [{
            "id": t.id,
            "date": t.date,
            "description": t.description,
            "amount": float(t.amount) if t.amount is not None else None,
            "type": t.tx_type,
            "category": t.category,
            "running_balance": float(t.running_balance) if t.running_balance is not None else None,
        } for t in transactions]
        content = __import__("json").dumps(data, indent=2)
        media_type = "application/json"
        ext = "json"
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "date", "description", "amount", "type", "category", "running_balance"])
        for t in transactions:
            writer.writerow([
                t.id, t.date, t.description,
                float(t.amount) if t.amount is not None else "",
                t.tx_type, t.category,
                float(t.running_balance) if t.running_balance is not None else "",
            ])
        content = output.getvalue()
        media_type = "text/csv"
        ext = "csv"
    elif format == "qif":
        lines = ["!Account", "NExported", "^", "!Type:Bank"]
        for t in transactions:
            lines.append(f"D{t.date}")
            lines.append(f"P{t.description}")
            lines.append(f"T{float(t.amount) if t.amount is not None else 0}")
            lines.append(f"L{t.category or ''}")
            lines.append("^")
        content = "\n".join(lines)
        media_type = "text/plain"
        ext = "qif"
    else:
        raise HTTPException(status_code=400, detail="Format must be json, csv, or qif")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="statement_{file_id}.{ext}"'},
    )
