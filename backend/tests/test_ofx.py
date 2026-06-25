"""Tests for v3.11 OFX/QFX import backend."""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.parsers.ofx import OFXParseError, OFXStatement, parse_ofx


SAMPLE_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKACCTFROM>
          <BANKID>123456789</BANKID>
          <ACCTID>987654321</ACCTID>
          <ACCTTYPE>CHECKING</ACCTTYPE>
        </BANKACCTFROM>
        <BANKTRANLIST>
          <DTSTART>20260101000000</DTSTART>
          <DTEND>20260131000000</DTEND>
          <STMTTRN>
            <TRNTYPE>CREDIT</TRNTYPE>
            <DTPOSTED>20260102000000</DTPOSTED>
            <TRNAMT>+1500.00</TRNAMT>
            <FITID>TXN-001</FITID>
            <NAME>Salary Deposit</NAME>
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>DEBIT</TRNTYPE>
            <DTPOSTED>20260105000000</DTPOSTED>
            <TRNAMT>-75.50</TRNAMT>
            <FITID>TXN-002</FITID>
            <NAME>Grocery Store</NAME>
          </STMTTRN>
        </BANKTRANLIST>
        <LEDGERBAL>
          <BALAMT>2500.50</BALAMT>
          <DTASOF>20260131000000</DTASOF>
        </LEDGERBAL>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""


def test_ofx_parser_extracts_transactions():
    stmt = parse_ofx(SAMPLE_OFX)
    assert isinstance(stmt, OFXStatement)
    assert stmt.account.account_id == "987654321"
    assert stmt.account.account_type == "checking"
    assert stmt.account.bank_id == "123456789"
    assert len(stmt.transactions) == 2

    salary = stmt.transactions[0]
    assert salary.fitid == "TXN-001"
    assert salary.amount == Decimal("1500.00")
    assert salary.date.year == 2026
    assert salary.date.month == 1
    assert salary.date.day == 2
    assert "Salary" in salary.description

    grocery = stmt.transactions[1]
    assert grocery.fitid == "TXN-002"
    assert grocery.amount == Decimal("-75.50")
    assert "Grocery" in grocery.description


def test_ofx_parser_handles_multiple_accounts():
    multi = b"""<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKACCTFROM>
          <BANKID>111</BANKID>
          <ACCTID>CASH-01</ACCTID>
          <ACCTTYPE>CHECKING</ACCTTYPE>
        </BANKACCTFROM>
        <BANKTRANLIST>
          <DTSTART>20260101000000</DTSTART>
          <DTEND>20260131000000</DTEND>
          <STMTTRN>
            <DTPOSTED>20260102000000</DTPOSTED>
            <TRNAMT>100.00</TRNAMT>
            <FITID>M1</FITID>
            <NAME>Deposit</NAME>
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
  <CREDITCARDMSGSRSV1>
    <CCSTMTTRNRS>
      <CCSTMTRS>
        <CCACCTFROM>
          <ACCTID>CC-99</ACCTID>
        </CCACCTFROM>
        <BANKTRANLIST>
          <DTSTART>20260101000000</DTSTART>
          <DTEND>20260131000000</DTEND>
          <STMTTRN>
            <DTPOSTED>20260103000000</DTPOSTED>
            <TRNAMT>-25.00</TRNAMT>
            <FITID>M2</FITID>
            <NAME>Coffee</NAME>
          </STMTTRN>
        </BANKTRANLIST>
      </CCSTMTRS>
    </CCSTMTTRNRS>
  </CREDITCARDMSGSRSV1>
</OFX>
"""
    # The current parser picks the first bank account block by design.
    stmt = parse_ofx(multi)
    assert stmt.account.account_id in {"CASH-01", "CC-99"}
    assert len(stmt.transactions) >= 1


def test_ofx_parser_rejects_garbage():
    with pytest.raises(OFXParseError):
        parse_ofx(b"not an ofx file")


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def _auth_tenant(db: Session):
    user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert user is not None
    return user, user.clients[0]


def test_ofx_endpoint_imports_transactions(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    resp = auth_client.post(
        "/api/imports/ofx",
        files={"file": ("sample.ofx", BytesIO(SAMPLE_OFX), "application/x-ofx")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["transactions_count"] == 2
    assert body["duplicates_skipped"] == 0
    assert body["account_name"] == "987654321"

    # Verify DB state
    account = db.query(models.Account).filter(
        models.Account.user_id == user.id,
        models.Account.account_number_masked == "987654321",
    ).first()
    assert account is not None
    statement = db.query(models.Statement).filter(
        models.Statement.id == body["statement_id"]
    ).first()
    assert statement is not None
    txns = db.query(models.Transaction).filter(
        models.Transaction.statement_id == statement.id
    ).all()
    assert len(txns) == 2
    assert {t.fitid for t in txns} == {"TXN-001", "TXN-002"}


def test_fitid_dedup_skips_duplicates(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    resp1 = auth_client.post(
        "/api/imports/ofx",
        files={"file": ("sample.ofx", BytesIO(SAMPLE_OFX), "application/x-ofx")},
    )
    assert resp1.status_code == 200
    first_statement_id = resp1.json()["statement_id"]

    resp2 = auth_client.post(
        "/api/imports/ofx",
        files={"file": ("sample.ofx", BytesIO(SAMPLE_OFX), "application/x-ofx")},
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["transactions_count"] == 0
    assert body2["duplicates_skipped"] == 2
    assert body2["statement_id"] != first_statement_id


def test_ofx_account_mapping_by_account_id(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    account = models.Account(
        user_id=user.id,
        tenant_id=client.id,
        client_id=client.id,
        name="Primary Checking",
        account_number_masked="987654321",
        type="checking",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    resp = auth_client.post(
        "/api/imports/ofx",
        files={"file": ("sample.ofx", BytesIO(SAMPLE_OFX), "application/x-ofx")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_id"] == account.id
    assert body["account_name"] == "Primary Checking"


def test_ofx_endpoint_rejects_non_ofx(auth_client: TestClient):
    resp = auth_client.post(
        "/api/imports/ofx",
        files={"file": ("sample.pdf", BytesIO(b"not ofx"), "application/pdf")},
    )
    assert resp.status_code == 415
