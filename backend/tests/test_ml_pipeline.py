"""Local ML pipeline tests (TASK-038.9).

Covers model training, manifest integrity hashing, safe model loading,
tamper detection, and the /api/ml/train endpoint.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from backend import models
from backend.local.ml_pipeline import (
    train_local_model,
    load_local_model_safe,
    load_local_model,
    predict_local,
    TrainingError,
    LOCAL_ROOT,
)
from backend.local.settings import LOCAL_ROOT as _LOCAL_ROOT


TRAINING_SEED: List[Dict[str, Any]] = [
    {"description": "STARBUCKS #123 MIAMI", "category": "Food & Dining"},
    {"description": "COFFEE BEAN LOS ANGELES", "category": "Food & Dining"},
    {"description": "MCDONALDS #456", "category": "Food & Dining"},
    {"description": "CHIPOTLE ORLANDO", "category": "Food & Dining"},
    {"description": "SHELL OIL 57443342312", "category": "Auto & Transport"},
    {"description": "CHEVRON 9876543", "category": "Auto & Transport"},
    {"description": "GEICO INSURANCE", "category": "Auto & Transport"},
    {"description": "PAYROLL DEPOSIT ACME", "category": "Income"},
    {"description": "SALARY PAYMENT", "category": "Income"},
    {"description": "DIRECT DEPOSIT TREASURY", "category": "Income"},
    {"description": "WALMART GROCERIES", "category": "Shopping"},
    {"description": "TARGET STORE 2341", "category": "Shopping"},
    {"description": "AMAZON.COM AMZN", "category": "Shopping"},
]


@pytest.fixture
def fresh_ml_dir(tmp_path: Path) -> Path:
    """Provide an isolated model directory and clean up after the test."""
    model_dir = tmp_path / "ml"
    model_dir.mkdir(parents=True, exist_ok=True)
    yield model_dir
    if model_dir.exists():
        shutil.rmtree(model_dir, ignore_errors=True)


def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_train_local_model_creates_manifest_with_hash(fresh_ml_dir: Path) -> None:
    result = train_local_model(TRAINING_SEED, model_dir=fresh_ml_dir)

    meta_path = fresh_ml_dir / "model_meta.json"
    assert meta_path.exists(), "Manifest should be written"
    meta = json.loads(meta_path.read_text())

    assert "model_sha256" in meta
    assert "vectorizer_sha256" in meta
    assert "trained_at" in meta
    assert meta.get("version") == 1
    assert meta["model_sha256"] == result.model_sha256
    assert meta["model_sha256"] == _sha256_file(result.model_path)
    assert meta["vectorizer_sha256"] == _sha256_file(result.vectorizer_path)


def test_load_local_model_safe_succeeds_with_valid_manifest(fresh_ml_dir: Path) -> None:
    train_local_model(TRAINING_SEED, model_dir=fresh_ml_dir)
    model = load_local_model_safe(fresh_ml_dir)
    assert model is not None, "Valid model should load"

    category, confidence = predict_local("STARBUCKS COFFEE", model=model)
    assert isinstance(category, str)
    assert category in {tx["category"] for tx in TRAINING_SEED}
    assert 0.0 <= confidence <= 1.0


def test_load_local_model_safe_rejects_tampered_model(fresh_ml_dir: Path) -> None:
    train_local_model(TRAINING_SEED, model_dir=fresh_ml_dir)

    model_path = fresh_ml_dir / "local_model.pkl"
    original = model_path.read_bytes()
    model_path.write_bytes(original[:-8] + b"TAMPERED")

    with pytest.raises(TrainingError, match="integrity"):
        load_local_model_safe(fresh_ml_dir)


def test_load_local_model_safe_rejects_missing_manifest(fresh_ml_dir: Path) -> None:
    train_local_model(TRAINING_SEED, model_dir=fresh_ml_dir)

    meta_path = fresh_ml_dir / "model_meta.json"
    meta_path.unlink()

    assert load_local_model_safe(fresh_ml_dir) is None


def test_load_local_model_delegates_to_safe_loader(fresh_ml_dir: Path) -> None:
    train_local_model(TRAINING_SEED, model_dir=fresh_ml_dir)
    assert load_local_model(fresh_ml_dir) is not None

    # Tamper and confirm delegation rejects it.
    model_path = fresh_ml_dir / "local_model.pkl"
    model_path.write_bytes(model_path.read_bytes()[:-4] + b"BAD")
    with pytest.raises(TrainingError, match="integrity"):
        load_local_model(fresh_ml_dir)


def test_ml_train_endpoint_requires_authentication(client: TestClient) -> None:
    resp = client.post("/api/ml/train")
    assert resp.status_code == 401


def _boot_admin(client: TestClient) -> str:
    password = "T4xFl0w!ML-T3st-Adm1n-2026"
    resp = client.post("/api/auth/boot", json={"password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _seed_labeled_transactions(db, user_id: int, tenant_id: int, count: int = 13) -> None:
    from backend.models import Account, Statement, Transaction
    from datetime import date

    client_row = db.query(models.Client).filter(models.Client.user_id == user_id).first()
    if client_row is None:
        client_row = models.Client(name="ML Test Client", user_id=user_id)
        db.add(client_row)
        db.commit()
        db.refresh(client_row)

    account = Account(
        name="Checking",
        client_id=client_row.id,
        tenant_id=client_row.id,
        user_id=user_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    statement = Statement(
        account_id=account.id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)

    for i, tx in enumerate(TRAINING_SEED[:count]):
        db.add(
            Transaction(
                statement_id=statement.id,
                tenant_id=tenant_id,
                user_id=user_id,
                date=date(2026, 6, 1),
                description=tx["description"],
                amount=10.0 * (i + 1),
                category=tx["category"],
            )
        )
    db.commit()


def test_ml_train_endpoint_insufficient_labels(client: TestClient) -> None:
    token = _boot_admin(client)
    resp = client.post("/api/ml/train", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
    assert "10" in resp.json()["detail"]


def test_ml_train_endpoint_succeeds(client: TestClient, db, fresh_ml_dir: Path, monkeypatch) -> None:
    """Train endpoint returns a model and persists a registry row in the active test DB."""
    token = _boot_admin(client)

    # Keep model artifacts inside the isolated fixture directory.
    monkeypatch.setattr("backend.local.ml_pipeline.LOCAL_ROOT", fresh_ml_dir.parent)
    monkeypatch.setattr("backend.routers.ml.local_settings.LOCAL_ROOT", fresh_ml_dir.parent)

    user = db.query(models.User).first()
    assert user is not None, "boot endpoint should have created the admin user"
    user_id = user.id
    _seed_labeled_transactions(db, user_id, user_id)

    resp = client.post("/api/ml/train", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "model_sha256" in data
    assert "version" in data
    assert data["version"] >= 1
    assert data["support"] >= 10

    registry = db.query(models.TrainedModel).filter(
        models.TrainedModel.user_id == user_id,
        models.TrainedModel.is_active == True,
    ).first()
    assert registry is not None
    assert registry.model_sha256 == data["model_sha256"]


def test_predict_local_falls_back_to_keyword_categorize(client: TestClient) -> None:
    from backend.routers.ml import categorize
    assert categorize("STARBUCKS #123") == "Food & Dining"
    assert categorize("SHELL OIL 12345") == "Auto & Transport"
