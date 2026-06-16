"""
Settings router: firm settings management, logo upload, recurring thresholds.
- GET/PUT firm settings
- Logo upload to data/logos/
- Recurring threshold management
"""
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

LOGOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "logos")


class ThresholdsResponse(BaseModel):
    high_confidence: float
    medium_confidence: float
    auto_confirm: float


DEFAULT_THRESHOLDS = {
    "high_confidence": 0.85,
    "medium_confidence": 0.60,
    "auto_confirm": 0.95,
}


def _get_or_create_settings(db: Session, tenant_id: int) -> models.FirmSettings:
    settings = (
        db.query(models.FirmSettings)
        .filter(models.FirmSettings.tenant_id == tenant_id)
        .first()
    )
    if not settings:
        settings = models.FirmSettings(
            tenant_id=tenant_id,
            firm_name=None,
            firm_address=None,
            firm_phone=None,
            firm_email=None,
            firm_ein=None,
            logo_path=None,
            fiscal_year_end=None,
            timezone="America/New_York",
            date_format="%m/%d/%Y",
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("", response_model=schemas.FirmSettings)
def get_settings(
    client_id: int = Query(..., description="Client ID (tenant)"),
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

    settings = _get_or_create_settings(db, client_id)
    return settings


@router.put("", response_model=schemas.FirmSettings)
def update_settings(
    client_id: int = Query(..., description="Client ID (tenant)"),
    data: schemas.FirmSettingsCreate = ...,
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

    settings = _get_or_create_settings(db, client_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="settings_update",
        entity_type="firm_settings",
        entity_id=settings.id,
        details="Updated firm settings",
    )
    db.add(audit)
    db.commit()

    return settings


@router.post("/logo/upload", status_code=status.HTTP_200_OK)
async def upload_logo(
    client_id: int = Query(..., description="Client ID (tenant)"),
    file: UploadFile = File(..., description="Logo image (PNG/JPG)"),
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

    original_ext = os.path.splitext(file.filename or "logo.bin")[1].lower()
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
    if original_ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {original_ext}. Allowed: {', '.join(allowed)}",
        )

    os.makedirs(LOGOS_DIR, exist_ok=True)
    unique_name = f"logo_{client_id}_{uuid.uuid4().hex}{original_ext}"
    file_path = os.path.join(LOGOS_DIR, unique_name)

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save logo: {str(exc)}",
        )

    settings = _get_or_create_settings(db, client_id)

    # Remove old logo file
    if settings.logo_path and os.path.exists(settings.logo_path) and settings.logo_path != file_path:
        try:
            os.remove(settings.logo_path)
        except OSError:
            pass

    settings.logo_path = file_path
    db.commit()
    db.refresh(settings)

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="logo_upload",
        entity_type="firm_settings",
        entity_id=settings.id,
        details=f"Uploaded logo {file.filename}",
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Logo uploaded successfully",
        "logo_path": file_path,
        "filename": unique_name,
    }


@router.get("/recurring-thresholds", response_model=ThresholdsResponse)
def get_thresholds(
    client_id: int = Query(..., description="Client ID (tenant)"),
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

    # Thresholds stored as a JSON-like approach in a dedicated table file
    # For simplicity, read from a local SQLite store
    thresholds = _read_thresholds(client_id)
    return ThresholdsResponse(**thresholds)


@router.put("/recurring-thresholds", response_model=ThresholdsResponse)
def update_thresholds(
    client_id: int = Query(..., description="Client ID (tenant)"),
    data: ThresholdsResponse = ...,
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

    if not (0 <= data.high_confidence <= 1):
        raise HTTPException(status_code=400, detail="high_confidence must be between 0 and 1")
    if not (0 <= data.medium_confidence <= 1):
        raise HTTPException(status_code=400, detail="medium_confidence must be between 0 and 1")
    if not (0 <= data.auto_confirm <= 1):
        raise HTTPException(status_code=400, detail="auto_confirm must be between 0 and 1")
    if data.high_confidence < data.medium_confidence:
        raise HTTPException(status_code=400, detail="high_confidence must be >= medium_confidence")

    new_vals = {
        "high_confidence": data.high_confidence,
        "medium_confidence": data.medium_confidence,
        "auto_confirm": data.auto_confirm,
    }
    _write_thresholds(client_id, new_vals)

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="thresholds_update",
        entity_type="firm_settings",
        entity_id=client_id,
        details=f"Updated thresholds: {new_vals}",
    )
    db.add(audit)
    db.commit()

    return ThresholdsResponse(**new_vals)


def _thresholds_db_path() -> str:
    tdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
    os.makedirs(tdir, exist_ok=True)
    return os.path.join(tdir, "thresholds.db")


def _read_thresholds(client_id: int) -> dict:
    import sqlite3
    db_path = _thresholds_db_path()
    if not os.path.exists(db_path):
        return DEFAULT_THRESHOLDS.copy()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS recurring_thresholds (client_id INTEGER PRIMARY KEY, high REAL, medium REAL, auto REAL)"
    )
    cur.execute("SELECT * FROM recurring_thresholds WHERE client_id = ?", (client_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "high_confidence": row["high"],
            "medium_confidence": row["medium"],
            "auto_confirm": row["auto"],
        }
    return DEFAULT_THRESHOLDS.copy()


def _write_thresholds(client_id: int, vals: dict):
    import sqlite3
    db_path = _thresholds_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS recurring_thresholds (client_id INTEGER PRIMARY KEY, high REAL, medium REAL, auto REAL)"
    )
    cur.execute(
        "INSERT OR REPLACE INTO recurring_thresholds (client_id, high, medium, auto) VALUES (?, ?, ?, ?)",
        (client_id, vals["high_confidence"], vals["medium_confidence"], vals["auto_confirm"]),
    )
    conn.commit()
    conn.close()
