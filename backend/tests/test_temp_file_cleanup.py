"""Tests for temporary file cleanup (TASK-035)."""
from __future__ import annotations

import io
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api_utils import get_upload_dir
from backend.parsers.ocr_parser import OCRPDFParser
from backend.utils.temp_file_cleanup import (
    TemporaryOCRDirectory,
    cleanup_old_temp_files,
    cleanup_uploaded_file,
)


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"


class TestTemporaryOCRDirectory:
    def test_creates_and_removes_directory(self):
        with TemporaryOCRDirectory() as tmp_dir:
            assert tmp_dir.exists()
            assert tmp_dir.is_dir()
            (tmp_dir / "scratch.png").write_text("image", encoding="utf-8")
        assert not tmp_dir.exists()

    def test_removes_directory_on_exception(self):
        tmp_dir = None
        with pytest.raises(RuntimeError):
            with TemporaryOCRDirectory() as d:
                tmp_dir = d
                (d / "scratch.png").write_text("image", encoding="utf-8")
                raise RuntimeError("boom")
        assert tmp_dir is not None
        assert not tmp_dir.exists()


class TestCleanupUploadedFile:
    def test_deletes_file(self, tmp_path: Path):
        target = tmp_path / "uploaded.pdf"
        target.write_text("pdf", encoding="utf-8")
        assert cleanup_uploaded_file(target) is True
        assert not target.exists()

    def test_returns_true_for_missing_file(self, tmp_path: Path):
        target = tmp_path / "missing.pdf"
        assert cleanup_uploaded_file(target) is True


class TestCleanupOldTempFiles:
    def test_deletes_old_upload_files(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(
            "backend.utils.temp_file_cleanup.get_upload_dir", lambda: tmp_path
        )
        old = tmp_path / "old_upload.pdf"
        old.write_text("pdf", encoding="utf-8")
        # Set mtime well in the past.
        past = time.time() - 48 * 3600
        old.touch(exist_ok=True)
        import os

        os.utime(str(old), (past, past))

        recent = tmp_path / "recent_upload.pdf"
        recent.write_text("pdf", encoding="utf-8")

        summary = cleanup_old_temp_files(max_age_hours=24.0)
        assert summary[str(tmp_path)] == 1
        assert not old.exists()
        assert recent.exists()

    def test_deletes_old_ocr_temp_files(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
        old_ocr = tmp_path / "pdf2image_abc.png"
        old_ocr.write_text("image", encoding="utf-8")
        past = time.time() - 48 * 3600
        import os

        os.utime(str(old_ocr), (past, past))

        summary = cleanup_old_temp_files(max_age_hours=24.0)
        assert summary[str(tmp_path)] == 1
        assert not old_ocr.exists()


class TestUploadRouterCleanup:
    def test_uploaded_pdf_deleted_after_success(self, auth_client: TestClient, valid_pdf_bytes, tmp_path, monkeypatch):
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

        monkeypatch.setattr("backend.utils.temp_file_cleanup.get_upload_dir", lambda: tmp_path)
        # Mock sandbox to avoid parser/OCR/audit paths; this test is about cleanup.
        monkeypatch.setattr(
            "backend.routers.upload.run_in_sandbox",
            lambda *args, **kwargs: {
                "reconciliation": {},
                "meta": {},
                "transactions": [],
                "needs_review": False,
            },
        )
        # Avoid the append-only audit path; not under test here.
        monkeypatch.setattr("backend.routers.upload.record", lambda *args, **kwargs: None)

        data = {"file": ("statement.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")}
        resp = auth_client.post("/api/upload", params={"account_id": account_id}, files=data)
        assert resp.status_code == 200, resp.text

        # The uploaded scratch file should be gone.
        uploaded = list(tmp_path.glob("*_statement.pdf"))
        assert not uploaded, f"Expected uploaded PDF to be deleted, found: {uploaded}"

    def test_uploaded_pdf_deleted_after_sandbox_failure(self, auth_client: TestClient, valid_pdf_bytes, tmp_path, monkeypatch):
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

        monkeypatch.setattr("backend.utils.temp_file_cleanup.get_upload_dir", lambda: tmp_path)
        # Avoid the append-only audit path; not under test here.
        monkeypatch.setattr("backend.routers.upload.record", lambda *args, **kwargs: None)

        from backend.parsers.sandbox import SandboxError

        def _failing_sandbox(*args, **kwargs):
            raise SandboxError("forced failure")

        monkeypatch.setattr("backend.routers.upload.run_in_sandbox", _failing_sandbox)

        data = {"file": ("statement.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")}
        resp = auth_client.post("/api/upload", params={"account_id": account_id}, files=data)
        assert resp.status_code == 422, resp.text

        uploaded = list(tmp_path.glob("*_statement.pdf"))
        assert not uploaded, f"Expected uploaded PDF to be deleted after failure, found: {uploaded}"


class TestOCRParserCleanup:
    def test_ocr_parser_raises_on_unavailable_deps(self, tmp_path: Path, monkeypatch):
        """If OCR deps are unavailable, construction should raise before creating temp dirs."""
        # Patch supported() to False so we don't need real OCR binaries.
        monkeypatch.setattr(OCRPDFParser, "supported", classmethod(lambda cls: False))
        with pytest.raises(RuntimeError):
            OCRPDFParser(str(tmp_path / "fake.pdf"))
