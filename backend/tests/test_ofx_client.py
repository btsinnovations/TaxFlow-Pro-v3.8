"""Tests for the OFX client service."""

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.services.ofx_client import (
    OFXClient,
    OFXTransaction,
    build_ofx_request,
    encrypt_password,
    decrypt_password,
    parse_ofx_response,
)


class TestPasswordEncryption:
    def test_round_trip_with_generated_key(self):
        from cryptography.fernet import Fernet
        fernet_key = Fernet.generate_key()
        password = "my_secret_password"
        encrypted = encrypt_password(password, key=fernet_key)
        assert encrypted != password
        decrypted = decrypt_password(encrypted, key=fernet_key)
        assert decrypted == password


class TestRequestBuilder:
    def test_build_request_contains_required_tags(self):
        request = build_ofx_request(
            username="testuser",
            password="testpass",
            org="BANK",
            institution_id="12345",
            account_id="67890",
            account_type="CHECKING",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert "OFXHEADER:100" in request
        assert "<SIGNONMSGSRQV1>" in request
        assert "<BANKMSGSRQV1>" in request
        assert "testuser" in request
        assert "67890" in request
        assert "CHECKING" in request
        assert "20240101000000" in request
        assert "20241231000000" in request

    def test_xml_escaping(self):
        request = build_ofx_request(
            username="user&name",
            password="pass<word>",
            org="BANK",
            institution_id="12345",
            account_id="67890",
            account_type="CHECKING",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert "user&amp;name" in request
        assert "pass&lt;word&gt;" in request


class TestResponseParser:
    SAMPLE_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:220
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:fake-uid

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>USD</CURDEF>
<BANKACCTFROM>
<BANKID>12345</BANKID>
<ACCTID>67890</ACCTID>
<ACCTTYPE>CHECKING</ACCTTYPE>
</BANKACCTFROM>
<LEDGERBAL>
<BALAMT>1234.56</BALAMT>
<DTASOF>20241231</DTASOF>
</LEDGERBAL>
<TRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20240315</DTPOSTED>
<TRNAMT>-25.50</TRNAMT>
<FITID>TXN001</FITID>
<NAME>COFFEE SHOP</NAME>
<MEMO>Breakfast</MEMO>
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20240320</DTPOSTED>
<TRNAMT>1500.00</TRNAMT>
<FITID>TXN002</FITID>
<NAME>PAYCHECK</NAME>
<MEMO>Salary</MEMO>
</STMTTRN>
</TRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""

    def test_parse_transactions(self):
        transactions, account_info = parse_ofx_response(self.SAMPLE_OFX)
        assert len(transactions) == 2
        assert transactions[0].fitid == "TXN001"
        assert transactions[0].amount == -25.50
        assert transactions[0].date_posted == date(2024, 3, 15)
        assert transactions[1].fitid == "TXN002"
        assert transactions[1].amount == 1500.00

    def test_parse_account_info(self):
        transactions, account_info = parse_ofx_response(self.SAMPLE_OFX)
        assert account_info is not None
        assert account_info.account_id == "67890"
        assert account_info.balance == 1234.56
        assert account_info.currency == "USD"
        assert account_info.date_as_of == date(2024, 12, 31)

    def test_parse_invalid_response(self):
        with pytest.raises(ValueError, match="Invalid OFX response"):
            parse_ofx_response("not an ofx response")


class TestOFXClient:
    def test_build_request(self):
        client = OFXClient(
            institution_id="12345",
            org="BANK",
            url="https://ofx.example.com",
            username="user",
            password="pass",
            account_id="67890",
            account_type="CHECKING",
        )
        payload = client.build_request(date(2024, 1, 1), date(2024, 12, 31))
        assert "user" in payload
        assert "67890" in payload

    @patch("backend.services.ofx_client.requests.post")
    def test_fetch_transactions(self, mock_post):
        mock_response = MagicMock()
        mock_response.text = TestResponseParser.SAMPLE_OFX
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = OFXClient(
            institution_id="12345",
            org="BANK",
            url="https://ofx.example.com",
            username="user",
            password="pass",
            account_id="67890",
            account_type="CHECKING",
        )
        transactions = client.fetch_transactions(date(2024, 1, 1), date(2024, 12, 31))
        assert len(transactions) == 2
        assert transactions[0].date_posted <= transactions[1].date_posted
        mock_post.assert_called_once()

    @patch("backend.services.ofx_client.requests.post")
    def test_fetch_balance(self, mock_post):
        mock_response = MagicMock()
        mock_response.text = TestResponseParser.SAMPLE_OFX
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = OFXClient(
            institution_id="12345",
            org="BANK",
            url="https://ofx.example.com",
            username="user",
            password="pass",
            account_id="67890",
            account_type="CHECKING",
        )
        account_info = client.fetch_balance()
        assert account_info.balance == 1234.56
        assert account_info.currency == "USD"
