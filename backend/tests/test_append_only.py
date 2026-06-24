"""Tests for append-only audit entry enforcement."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend import models
from backend.audit import record, verify_chain, AuditAction, AuditResource
from backend.tests.conftest import override_get_db
from backend.database import Base
from backend.tests.conftest import engine as test_engine


def _make_user(db: Session, username: str) -> models.User:
    user = models.User(username=username, email=f"{username}@local", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=test_engine)
    db = next(override_get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=test_engine)


def test_audit_entry_insert_still_works(db: Session):
    user = _make_user(db, "append1")
    entry = record(db, user, AuditAction.CREATE, AuditResource.CLIENT, 1)
    assert entry.id is not None
    valid, bad_id = verify_chain(db)
    assert valid
    assert bad_id is None


def test_orm_update_audit_entry_blocked(db: Session):
    user = _make_user(db, "append2")
    entry = record(db, user, AuditAction.CREATE, AuditResource.CLIENT, 1)

    with pytest.raises(Exception):
        db.execute(
            text("UPDATE audit_entries SET action = 'tampered' WHERE id = :id"),
            {"id": entry.id},
        )
        db.commit()

    # Chain should still verify cleanly after blocked update.
    valid, bad_id = verify_chain(db)
    assert valid
    assert bad_id is None


def test_orm_delete_audit_entry_blocked(db: Session):
    user = _make_user(db, "append3")
    entry = record(db, user, AuditAction.CREATE, AuditResource.CLIENT, 1)

    with pytest.raises(Exception):
        db.execute(
            text("DELETE FROM audit_entries WHERE id = :id"),
            {"id": entry.id},
        )
        db.commit()

    # Row should still exist and chain should verify.
    rows = db.execute(text("SELECT COUNT(*) FROM audit_entries")).scalar()
    assert rows == 1
    valid, bad_id = verify_chain(db)
    assert valid
    assert bad_id is None
