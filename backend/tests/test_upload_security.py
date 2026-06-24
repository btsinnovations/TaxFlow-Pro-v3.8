"""Upload security tests for TaxFlow Pro v3.9."""
from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.security.upload_validator import (
    validate_upload_file,
    MAX_UPLOAD_SIZE_BYTES,
)


class _FakeUploadFile:
    """Minimal UploadFile stand-in for unit tests."""

    def __init__(self, filename: str, content: bytes, content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._body = content

    async def read(self, n: int = -1) -> bytes:
        if n == -1:
            return self._body
        chunk = self._body[:n]
        self._body = self._body[n:]
        return chunk


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"


@pytest.mark.anyio
async def test_valid_pdf_passes(valid_pdf_bytes):
    fake = _FakeUploadFile("statement.pdf", valid_pdf_bytes)
    contents = await validate_upload_file(fake, "statement.pdf")
    assert contents == valid_pdf_bytes


@pytest.mark.anyio
async def test_oversized_pdf_rejected(valid_pdf_bytes, monkeypatch):
    # Patch the limit temporarily so the test runs quickly.
    limit = len(valid_pdf_bytes)
    monkeypatch.setenv("TAXFLOW_MAX_UPLOAD_BYTES", str(limit))

    from backend.security import upload_validator
    monkeypatch.setattr(upload_validator, "MAX_UPLOAD_SIZE_BYTES", limit)

    oversized = valid_pdf_bytes + b"EXTRA"
    fake = _FakeUploadFile("statement.pdf", oversized)
    with pytest.raises(Exception) as exc_info:
        await validate_upload_file(fake, "statement.pdf")
    assert exc_info.value.status_code == 413


@pytest.mark.anyio
async def test_wrong_extension_rejected(valid_pdf_bytes):
    fake = _FakeUploadFile("statement.exe", valid_pdf_bytes)
    with pytest.raises(Exception) as exc_info:
        await validate_upload_file(fake, "statement.exe")
    assert exc_info.value.status_code == 415


@pytest.mark.anyio
async def test_wrong_mime_type_rejected(valid_pdf_bytes):
    fake = _FakeUploadFile("statement.pdf", valid_pdf_bytes, content_type="image/png")
    with pytest.raises(Exception) as exc_info:
        await validate_upload_file(fake, "statement.pdf")
    assert exc_info.value.status_code == 415


@pytest.mark.anyio
async def test_fake_extension_no_magic_bytes_rejected():
    fake = _FakeUploadFile("statement.pdf", b"This is not a PDF file", content_type="application/pdf")
    with pytest.raises(Exception) as exc_info:
        await validate_upload_file(fake, "statement.pdf")
    assert exc_info.value.status_code == 415


@pytest.mark.anyio
async def test_empty_file_rejected():
    fake = _FakeUploadFile("statement.pdf", b"", content_type="application/pdf")
    with pytest.raises(Exception) as exc_info:
        await validate_upload_file(fake, "statement.pdf")
    assert exc_info.value.status_code == 415


def test_endpoint_accepts_valid_pdf(auth_client: TestClient, valid_pdf_bytes):
    from backend.tests.conftest import TestingSessionLocal, _create_test_user
    from backend.models import Client, Account

    db = TestingSessionLocal()
    account_id = None
    try:
        user = _create_test_user(db)
        client = Client(name="Test Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
        account = Account(
            name="Checking",
            type="checking",
            client_id=client.id,
            tenant_id=client.id,
            user_id=user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        account_id = account.id
    finally:
        db.close()

    data = {
        "file": ("statement.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")
    }
    resp = auth_client.post("/api/upload", params={"account_id": account_id}, files=data)
    # A valid minimal PDF may not parse into transactions, but validation should allow it.
    assert resp.status_code != 415
    assert resp.status_code != 413


def test_endpoint_rejects_oversized_file(auth_client: TestClient, valid_pdf_bytes, monkeypatch):
    limit = len(valid_pdf_bytes)
    monkeypatch.setattr(
        "backend.security.upload_validator.MAX_UPLOAD_SIZE_BYTES", limit
    )

    data = {
        "file": (
            "statement.pdf",
            io.BytesIO(valid_pdf_bytes + b"EXTRA"),
            "application/pdf",
        )
    }
    resp = auth_client.post("/api/upload", files=data)
    assert resp.status_code == 413


def test_endpoint_rejects_non_pdf_extension(auth_client: TestClient, valid_pdf_bytes):
    data = {"file": ("statement.exe", io.BytesIO(valid_pdf_bytes), "application/pdf")}
    resp = auth_client.post("/api/upload", files=data)
    assert resp.status_code == 415


def test_endpoint_rejects_fake_pdf_magic(auth_client: TestClient):
    data = {"file": ("statement.pdf", io.BytesIO(b"not a pdf"), "application/pdf")}
    resp = auth_client.post("/api/upload", files=data)
    assert resp.status_code == 415
