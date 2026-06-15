"""Tests for the unified backend/parsers package and pipeline wrapper."""
import os
import sys
import tempfile
from pathlib import Path
from typing import List

import pytest
from fpdf import FPDF

# Ensure project root is on sys.path so backend.parsers imports work when pytest
# is invoked from backend/tests as well as from the project root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.parsers import (
    GenericPDFParser,
    parse_pdf_to_dict,
    parse_pdf_to_transactions,
    detect_institution,
    INSTITUTION_ALIASES,
    dict_to_backend_model,
    model_to_dict,
    deduplicate_dicts,
    ensure_tx_type,
)
from backend.parsers.generic_pdf import _detect_template


class _SimpleStmtPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Big Bank Statement", ln=True)
        self.cell(0, 10, "Statement Period: 01/01/2025 to 01/31/2025", ln=True)
        self.cell(0, 10, "Opening Balance: $100.00", ln=True)
        self.cell(0, 10, "Closing Balance: $100.00", ln=True)


def _make_pdf(lines: List[str]) -> str:
    pdf = _SimpleStmtPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    for line in lines:
        pdf.cell(0, 10, line, ln=True)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.output(tmp.name)
    return tmp.name


def test_generic_pdf_parser_output_shape():
    path = _make_pdf([
        "01/15/2025 Coffee Shop $5.00 $95.00",
        "01/20/2025 Salary Deposit $50.00 $100.00",
    ])
    try:
        result = parse_pdf_to_dict(path)
        assert "template" in result
        assert "account_info" in result
        assert "transactions" in result
        assert "reconciliation" in result
        assert "meta" in result
        assert len(result["transactions"]) == 2
        tx = result["transactions"][0]
        assert "date" in tx
        assert "description" in tx
        assert "amount" in tx
        assert "balance" in tx
    finally:
        os.unlink(path)


def test_parse_pdf_to_transactions_returns_list():
    path = _make_pdf([
        "01/15/2025 Coffee Shop $5.00 $95.00",
    ])
    try:
        txs = parse_pdf_to_transactions(path)
        assert isinstance(txs, list)
        assert len(txs) == 1
        assert "Coffee Shop" in txs[0]["description"]
    finally:
        os.unlink(path)


def test_detect_institution_known_brands():
    assert detect_institution("CHASE STATEMENT") == "Chase"
    assert detect_institution("TD Bank Statement") == "TD Bank"
    assert detect_institution("Your Chime checking statement") == "Chime"
    assert detect_institution("Cash App to Someone $10") == "Cash App"
    assert detect_institution("Educational Federal share draft") == "EdFed"


def test_detect_institution_unknown():
    assert detect_institution("Some Random PDF") == "unknown"


def test_ensure_tx_type():
    assert ensure_tx_type(5) == "credit"
    assert ensure_tx_type(-5) == "debit"
    assert ensure_tx_type("0") == "debit"


def test_deduplicate_dicts():
    txs = [
        {"date": "2025-01-15", "description": "Coffee Shop", "amount": 5.0},
        {"date": "2025-01-15", "description": "Coffee Shop", "amount": 5.0},
        {"date": "2025-01-16", "description": "Coffee Shop", "amount": 5.0},
    ]
    unique = deduplicate_dicts(txs)
    assert len(unique) == 2


def test_dict_to_backend_model():
    tx = {
        "date": "2025-01-15",
        "description": "Coffee",
        "amount": 5.0,
        "category": "Food",
        "balance": 95.0,
    }
    kwargs = dict_to_backend_model(tx, statement_id=1, tenant_id=2)
    assert kwargs["statement_id"] == 1
    assert kwargs["tenant_id"] == 2
    assert kwargs["tx_type"] == "credit"
    assert kwargs["amount"] == pytest.approx(5.0)
    assert kwargs["running_balance"] == pytest.approx(95.0)


def test_model_to_dict_roundtrip(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base
    from backend.models import Statement, Transaction

    db_path = tmp_path / "roundtrip.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        stmt = Statement(
            account_id=1, tenant_id=1, user_id=1, filename="x.pdf",
            period_start="2025-01-01", period_end="2025-01-31"
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
        tx = Transaction(
            statement_id=stmt.id, tenant_id=1, date="2025-01-15",
            description="Coffee", amount=5.0, tx_type="debit",
            category="Food", running_balance=95.0
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        d = model_to_dict(tx)
        assert d["id"] == tx.id
        assert d["amount"] == 5.0
        assert d["category"] == "Food"
    finally:
        db.close()


def test_phase3_wrapper_imports():
    """The phase3_pipeline wrapper must import without error and expose expected names."""
    from phase3_pipeline import pdf_parser
    assert callable(pdf_parser.pdf_to_transactions)
    assert hasattr(pdf_parser, "detect_institution")


def test_phase3_wrapper_falls_back_to_backend_parser(tmp_path):
    """When plugin registry returns nothing, the wrapper falls back to backend.parsers."""
    from phase3_pipeline.pdf_parser import pdf_to_transactions

    pdf_path = tmp_path / "stmt.pdf"
    pdf = _SimpleStmtPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, "01/15/2025 Grocery Store $12.50 $87.50", ln=True)
    pdf.output(str(pdf_path))

    transactions, raw_text = pdf_to_transactions(pdf_path)
    assert isinstance(transactions, list)
    assert raw_text != ""
    # At least the fallback path produces a transaction.
    assert len(transactions) >= 1
    assert transactions[0].institution is not None
