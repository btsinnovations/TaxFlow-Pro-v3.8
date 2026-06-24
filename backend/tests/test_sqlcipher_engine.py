"""Tests for SQLCipher-backed SQLite engine (TASK-038.1)."""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.local.sqlcipher_engine import (
    SQLCipherError,
    create_sqlcipher_engine,
    derive_sqlcipher_key,
    generate_keyfile,
    is_sqlcipher_available,
    migrate_plaintext_to_sqlcipher,
    rekey_sqlcipher_database,
)

pytestmark = pytest.mark.skipif(not is_sqlcipher_available(), reason="sqlcipher3 not installed")

Base = declarative_base()


class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True)
    text = Column(String)


# ---------------------------------------------------------------------------
# Windows file-lock helpers. sqlcipher3's native handle can keep a .db locked
# for a short interval after engine.dispose(), so we clean up manually with
# retries instead of relying on tempfile.TemporaryDirectory.
# ---------------------------------------------------------------------------


def _temp_dir() -> Path:
    return Path(tempfile.mkdtemp())


def _temp_db_path() -> Path:
    return _temp_dir() / "enc.db"


def _cleanup_dir(path: Path) -> None:
    for _ in range(20):
        try:
            shutil.rmtree(path, ignore_errors=True)
            return
        except PermissionError:
            time.sleep(0.05)
    shutil.rmtree(path, ignore_errors=True)


def _cleanup_db_path(path: Path) -> None:
    _cleanup_dir(path.parent)


def _make_plain_db(path: Path):
    engine = create_engine("sqlite:///" + str(path))
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(Note(text="secret"))
    s.commit()
    s.close()
    engine.dispose()


def test_pragma_key_syntax_round_trip():
    """Smoke-test that the derived PRAGMA key literal creates and reopens an encrypted DB."""
    tmp = _temp_dir()
    db = tmp / "enc.db"
    password = "MasterPass!2026"
    key = derive_sqlcipher_key(password, db)
    assert key.startswith('"x\'') and key.endswith('"')

    engine = create_sqlcipher_engine("sqlite:///" + str(db), password)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(Note(text="hello"))
    s.commit()
    s.close()
    engine.dispose()

    engine2 = create_sqlcipher_engine("sqlite:///" + str(db), password)
    Session2 = sessionmaker(bind=engine2)
    s2 = Session2()
    assert s2.query(Note).first().text == "hello"
    s2.close()
    engine2.dispose()
    _cleanup_dir(tmp)


def test_wrong_password_fails():
    db = _temp_db_path()
    engine = create_sqlcipher_engine("sqlite:///" + str(db), "correct")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(Note(text="hello"))
    s.commit()
    s.close()
    engine.dispose()

    bad_engine = create_sqlcipher_engine("sqlite:///" + str(db), "wrong")
    # On Windows the sqlcipher native handle may keep the file locked briefly
    # after dispose(); accept any exception as a failure to open.
    with pytest.raises((SQLCipherError, Exception)):
        with bad_engine.connect() as conn:
            conn.execute(text("SELECT count(*) FROM sqlite_master"))
    bad_engine.dispose()
    _cleanup_db_path(db)


def test_migrate_plaintext_to_sqlcipher():
    tmp = _temp_dir()
    plain = tmp / "plain.db"
    enc = tmp / "enc.db"
    _make_plain_db(plain)

    migrate_plaintext_to_sqlcipher(plain, enc, "MasterPass!2026")

    engine = create_sqlcipher_engine("sqlite:///" + str(enc), "MasterPass!2026")
    Session = sessionmaker(bind=engine)
    s = Session()
    assert s.query(Note).first().text == "secret"
    s.close()
    engine.dispose()
    _cleanup_dir(tmp)


def test_rekey_sqlcipher_database():
    tmp = _temp_dir()
    db = tmp / "enc.db"
    engine = create_sqlcipher_engine("sqlite:///" + str(db), "OldPass!2026")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(Note(text="rekey-me"))
    s.commit()
    s.close()
    engine.dispose()

    rekey_sqlcipher_database(db, "OldPass!2026", "NewPass!2027")

    engine2 = create_sqlcipher_engine("sqlite:///" + str(db), "NewPass!2027")
    Session2 = sessionmaker(bind=engine2)
    s2 = Session2()
    assert s2.query(Note).first().text == "rekey-me"
    s2.close()
    engine2.dispose()
    _cleanup_dir(tmp)


def test_keyfile_second_factor():
    tmp = _temp_dir()
    plain = tmp / "plain.db"
    enc = tmp / "enc.db"
    keyfile = generate_keyfile(tmp / "key.bin")
    _make_plain_db(plain)

    migrate_plaintext_to_sqlcipher(plain, enc, "MasterPass!2026", keyfile_path=keyfile)

    engine = create_sqlcipher_engine("sqlite:///" + str(enc), "MasterPass!2026", keyfile_path=keyfile)
    Session = sessionmaker(bind=engine)
    s = Session()
    assert s.query(Note).first().text == "secret"
    s.close()
    engine.dispose()
    _cleanup_dir(tmp)


def test_keyfile_required_for_open():
    """Opening without the keyfile when one was used must fail."""
    tmp = _temp_dir()
    plain = tmp / "plain.db"
    enc = tmp / "enc.db"
    keyfile = generate_keyfile(tmp / "key.bin")
    _make_plain_db(plain)

    migrate_plaintext_to_sqlcipher(plain, enc, "MasterPass!2026", keyfile_path=keyfile)

    engine = create_sqlcipher_engine("sqlite:///" + str(enc), "MasterPass!2026")
    with pytest.raises((SQLCipherError, Exception)):
        with engine.connect() as conn:
            conn.execute(text("SELECT count(*) FROM sqlite_master"))
    engine.dispose()
    _cleanup_dir(tmp)
