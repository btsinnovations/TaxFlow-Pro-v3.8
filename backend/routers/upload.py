import os
import shutil
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..parsers.sandbox import run_in_sandbox, SandboxError, SandboxTimeout
from ..parsers.pdf_guard import inspect_pdf, PDFGuardError
from ..api_utils import get_upload_dir, store_uploaded_file
from ..audit import record, AuditAction, AuditResource
from ..local.column_encryption import encrypt_for_user
from ..services.rules import apply_rules
from .auth import get_current_user
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings

from ..security.upload_validator import validate_upload_file, MAX_UPLOAD_SIZE_BYTES
from ..local.backup import auto_backup_after_import
from ..database import DATABASE_URL
from ..utils.temp_file_cleanup import cleanup_uploaded_file

router = APIRouter(prefix="/upload", tags=["upload"])


def _get_upload_dir() -> Path:
    """Resolve the upload directory dynamically to respect TAXFLOW_LOCAL_ROOT."""
    return get_upload_dir()


UPLOAD_DIR = _get_upload_dir()


def to_decimal(value):
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(',', '').replace('$', '').strip()
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        return None

def standardize_date(date_str: str) -> Optional[date]:
    """Normalize a date string to a Python date object or return None."""
    from datetime import date as _date
    if not date_str:
        return None
    if isinstance(date_str, _date):
        return date_str
    date_str = str(date_str).strip()
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        try:
            return _date.fromisoformat(date_str)
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


from phase3_pipeline.identity import IdentityService


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


def _transaction_account_label(account) -> str:
    """Best-effort account label for idempotency keying."""
    if not account:
        return ""
    parts = [p for p in (account.name, account.institution) if p]
    return " | ".join(parts)


def _upsert_transactions(db: Session, statement, current_user, transactions: list, account):
    """Insert or upsert transactions keyed by deterministic txn_uid."""
    institution = (account.institution or "") if account else ""
    account_label = _transaction_account_label(account)

    for tx in transactions:
        # --- ROUTER-LEVEL CLEANING: Scrub header bleed before DB insert ---
        description = clean_header_bleed(tx.get("description", ""))
        amount_dec = to_decimal(tx.get("amount"))
        tx_type = "credit" if amount_dec and amount_dec > 0 else "debit"
        txn_date = standardize_date(tx.get("date"))

        txn_uid = IdentityService.generate_transaction_uid(
            date=str(txn_date) if txn_date else "",
            description=description,
            amount=amount_dec,
            institution=institution,
            account=account_label,
        )

        existing = None
        if statement.tenant_id is not None:
            existing = db.query(models.Transaction).filter(
                models.Transaction.tenant_id == statement.tenant_id,
                models.Transaction.user_id == current_user.id,
                models.Transaction.txn_uid == txn_uid,
            ).first()

        if existing is not None:
            # Idempotent path: update the statement pointer and mutable fields
            # so re-imports converge to the latest source row, but do not create
            # a duplicate transaction.
            existing.statement_id = statement.id
            existing.date = txn_date
            existing.description = encrypt_for_user(description, current_user)
            existing.amount = amount_dec
            existing.tx_type = tx_type
            existing.running_balance = to_decimal(tx.get("running_balance"))
            existing.import_source = "upload_upsert"
        else:
            db_tx = models.Transaction(
                statement_id=statement.id,
                tenant_id=statement.tenant_id,
                user_id=current_user.id,
                date=txn_date,
                description=encrypt_for_user(description, current_user),
                amount=amount_dec,
                tx_type=tx_type,
                running_balance=to_decimal(tx.get("running_balance")),
                txn_uid=txn_uid,
                import_source="upload",
            )
            db.add(db_tx)

    db.commit()



def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    if local_settings.is_single_user():
        set_tenant_id(db, resolve_user_tenant_id(current_user))
        return
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    set_tenant_id(db, int(tenant_id))
    return int(tenant_id)

@router.post("/")
async def upload_statement(request: Request,
                           file: UploadFile = File(...),
                           account_id: Optional[int] = None,
                           force_ocr: bool = False,
                           db: Session = Depends(get_db),
                           current_user: models.User = Depends(get_current_user)):
    inferred_tenant_id = _wrap_tenant(request, db, current_user)

    # Do not accept multipart file uploads in GET requests.
    if request.method.upper() != "POST":
        raise HTTPException(status_code=405, detail="Method Not Allowed")

    validated_bytes = await validate_upload_file(file, file.filename)

    # Parent-process defense: inspect raw bytes before writing to disk / sandbox.
    try:
        guard_result = inspect_pdf(
            validated_bytes,
            max_size_bytes=32 * 1024 * 1024,
            max_pages=100,
        )
        if not guard_result.ok:
            raise PDFGuardError(guard_result.reason or "PDF failed safety checks")
    except PDFGuardError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    file_path = store_uploaded_file(current_user.id, file.filename, validated_bytes)
    try:
        result = run_in_sandbox(
            "backend.parsers.institution:parse_statement_pdf",
            str(file_path),
            {"force_ocr": force_ocr},
            timeout_seconds=30.0,
            max_memory_mb=512,
        )
    except SandboxTimeout:
        cleanup_uploaded_file(file_path)
        raise HTTPException(status_code=422, detail="PDF could not be parsed safely")
    except SandboxError:
        cleanup_uploaded_file(file_path)
        raise HTTPException(status_code=422, detail="PDF could not be parsed safely")

    # Best-effort deletion of the uploaded scratch PDF after parsing.
    cleanup_uploaded_file(file_path)

    stmt_data = result.get("reconciliation", {})
    meta = result.get("meta", {})

    if account_id is not None:
        account = db.query(models.Account).filter(
            models.Account.id == account_id,
            models.Account.user_id == current_user.id
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        tenant_id = account.tenant_id
    else:
        tenant_id = None

    statement = models.Statement(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        filename=encrypt_for_user(file.filename, current_user),
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
    record(db, current_user, AuditAction.CREATE, AuditResource.STATEMENT, statement.id,
           {"filename": statement.filename, "account_id": statement.account_id})

    _upsert_transactions(db, statement, current_user, result.get("transactions", []), account)

    # --- Apply categorization rules to imported transactions ---
    if statement.tenant_id is not None:
        imported_transactions = db.query(models.Transaction).filter(
            models.Transaction.statement_id == statement.id
        ).all()
        rules = db.query(models.CategorizationRule).filter(
            models.CategorizationRule.tenant_id == statement.tenant_id,
            models.CategorizationRule.user_id == current_user.id,
        ).all()
        apply_rules(imported_transactions, rules)
        db.commit()

    warnings = []
    if result.get("needs_review"):
        warnings.append("Statement parser flagged this upload for manual review; institution or layout was not recognized.")

    # Automatic encrypted backup after every successful import (TASK-038.11).
    if DATABASE_URL.startswith("sqlite:///") or DATABASE_URL.startswith("sqlcipher:///"):
        try:
            auto_backup_after_import(
                DATABASE_URL.replace("sqlite:///", "").replace("sqlcipher:///", ""),
                backup_dir=None,
            )
        except Exception:
            # Do not fail the import if the automatic backup cannot run.
            pass

    return {
        "statement_id": statement.id,
        "transactions_count": len(result.get("transactions", [])),
        "variance": float(statement.variance) if statement.variance is not None else None,
        "balanced": statement.is_balanced,
        "template": result.get("template"),
        "needs_review": result.get("needs_review", False),
        "warnings": warnings,
    }
