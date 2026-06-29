"""Tests for Phase 1 + Phase 2 bank statement parsers and layout families."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.parsers.banks.families import (
    BrokeragePdfFamily,
    CreditCardPdfFamily,
    CsvStandardFamily,
    OfxQfxFamily,
    PdfTableMultiFamily,
    PdfTableSimpleFamily,
)
from backend.parsers.banks.institution_registry import (
    InstitutionFamilyRegistry,
    detect_institution_family,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bank_statements"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class TestCsvStandardFamily:
    def test_parse_csv_with_date_description_amount_balance(self) -> None:
        content = _read("axos_checking.csv")
        result = CsvStandardFamily("Axos Bank").parse(content)
        assert result["template"] == "Axos Bank"
        assert len(result["transactions"]) == 4
        tx = result["transactions"][0]
        assert tx["date"] == "2026-01-02"
        assert tx["description"] == "DIRECT DEPOSIT PAYROLL"
        assert tx["amount"] == 2500.00
        assert tx["type"] == "credit"
        assert tx["balance"] == 2500.00

    def test_empty_csv_returns_needs_review(self) -> None:
        result = CsvStandardFamily("Unknown").parse(b"")
        assert result["needs_review"] is True
        assert result["transactions"] == []

    def test_csv_with_missing_date_header(self) -> None:
        result = CsvStandardFamily("Unknown").parse(b"Foo,Bar\na,b\n")
        assert result["needs_review"] is True


class TestOfxQfxFamily:
    def test_parse_ofx(self) -> None:
        content = _read("chase_ofx.ofx")
        result = OfxQfxFamily("Chase OFX").parse(content)
        assert len(result["transactions"]) == 2
        assert result["transactions"][0]["amount"] == 2500.00
        assert result["transactions"][1]["amount"] == -85.40
        assert result["transactions"][1]["type"] == "debit"

    def test_empty_ofx(self) -> None:
        result = OfxQfxFamily("Empty").parse(b"")
        assert result["needs_review"] is True

    def test_ofx_date_parsing(self) -> None:
        parser = OfxQfxFamily("Test")
        assert parser._parse_ofx_date("20260102") == "2026-01-02"
        assert parser._parse_ofx_date("2026-01-02") is None
        assert parser._parse_ofx_date("") is None


class TestPdfTableSimpleFamily:
    def test_parse_simple_pdf_text(self) -> None:
        content = _read("credit_human.pdf.txt")
        result = PdfTableSimpleFamily("Credit Human").parse(content)
        assert len(result["transactions"]) == 4
        assert result["transactions"][0]["description"] == "GROCERY PURCHASE"
        assert result["transactions"][0]["amount"] == -45.67

    def test_no_transactions(self) -> None:
        result = PdfTableSimpleFamily("Empty").parse(b"No dates or amounts here")
        assert result["needs_review"] is True


class TestPdfTableMultiFamily:
    def test_parse_multi_page_pdf_text(self) -> None:
        content = _read("hsbc_checking.pdf.txt")
        result = PdfTableMultiFamily("HSBC").parse(content)
        assert len(result["transactions"]) == 5
        tx = result["transactions"][-1]
        assert tx["description"] == "UTILITY BILL"
        assert tx["amount"] == -110.50

    def test_totals_line_breaks_table(self) -> None:
        content = b"Page 1 of 1\n01/01/2026 A -10.00\nTotals for period\n01/02/2026 B -20.00"
        result = PdfTableMultiFamily("Test").parse(content)
        # Only the first transaction before totals line should be captured
        assert len(result["transactions"]) == 1


class TestCreditCardPdfFamily:
    def test_parse_credit_card_pdf(self) -> None:
        content = _read("amex_statement.pdf.txt")
        result = CreditCardPdfFamily("American Express").parse(content)
        assert len(result["transactions"]) == 4
        assert result["transactions"][2]["description"] == "PAYMENT - THANK YOU"
        assert result["transactions"][2]["amount"] == 1500.00
        assert result["transactions"][2]["type"] == "credit"

    def test_purchase_negative(self) -> None:
        content = b"01/02/2026 01/03 SUPERMARKET -78.45\n"
        result = CreditCardPdfFamily("Amex").parse(content)
        assert result["transactions"][0]["amount"] == -78.45


class TestBrokeragePdfFamily:
    def test_parse_brokerage_cash_section(self) -> None:
        content = _read("schwab_brokerage.pdf.txt")
        result = BrokeragePdfFamily("Charles Schwab").parse(content)
        # Holdings section is ignored; only cash transactions are parsed
        assert len(result["transactions"]) == 3
        assert result["transactions"][0]["amount"] == 125.00
        assert result["transactions"][1]["amount"] == -1000.00

    def test_holdings_only_ignored(self) -> None:
        content = b"Holdings\nSYMBOL QTY PRICE\nSPY 100 450.00\n"
        result = BrokeragePdfFamily("Schwab").parse(content)
        assert result["needs_review"] is True


class TestInstitutionRegistry:
    def test_registry_loads_all_institutions(self) -> None:
        reg = InstitutionFamilyRegistry()
        institutions = reg.all_institutions()
        assert len(institutions) >= 100

    @pytest.mark.parametrize(
        "filename, expected_family, min_confidence",
        [
            ("axos_checking.csv", "csv_standard", 0.80),
            ("chase_ofx.ofx", "ofx_qfx", 0.80),
            ("credit_human.pdf.txt", "pdf_table_simple", 0.30),
            ("hsbc_checking.pdf.txt", "pdf_table_multi", 0.30),
            ("amex_statement.pdf.txt", "credit_card_pdf", 0.30),
            ("schwab_brokerage.pdf.txt", "brokerage_pdf", 0.30),
        ],
    )
    def test_detect_family(self, filename: str, expected_family: str, min_confidence: float) -> None:
        content = _read(filename)
        result = detect_institution_family(content, filename=filename)
        assert result["family"] == expected_family
        assert result["confidence"] >= min_confidence

    def test_get_parser_for_each_family(self) -> None:
        reg = InstitutionFamilyRegistry()
        for family in [
            "csv_standard",
            "ofx_qfx",
            "pdf_table_simple",
            "pdf_table_multi",
            "credit_card_pdf",
            "brokerage_pdf",
        ]:
            parser = reg.get_parser(family, "Test Bank")
            assert parser is not None


class TestCsvStandardFamilyExtended:
    """Additional CSV family coverage without extra fixtures."""

    def test_posted_date_header(self) -> None:
        content = b"Posted Date,Description,Amount,Balance\n01/02/2026,Paycheck,1000.00,1000.00\n"
        result = CsvStandardFamily("Test").parse(content)
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["amount"] == 1000.00

    def test_debit_credit_columns(self) -> None:
        content = b"Date,Description,Debit,Credit\n01/02/2026,Paycheck,,1000.00\n01/03/2026,Groceries,45.67,\n"
        result = CsvStandardFamily("Test").parse(content)
        assert len(result["transactions"]) == 2
        assert result["transactions"][0]["amount"] == 1000.00
        assert result["transactions"][1]["amount"] == -45.67

    def test_csv_with_quoted_fields(self) -> None:
        content = b'Date,Description,Amount\n"01/02/2026","PAYCHECK, DIRECT",1000.00\n'
        result = CsvStandardFamily("Test").parse(content)
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["description"] == "PAYCHECK, DIRECT"

    def test_csv_missing_amount_columns(self) -> None:
        content = b"Date,Description,Balance\n01/02/2026,Paycheck,1000.00\n"
        result = CsvStandardFamily("Test").parse(content)
        assert result["needs_review"] is True

    def test_csv_extra_columns_ignored(self) -> None:
        content = b"Date,Description,Amount,Balance,Check,Foo\n01/02/2026,Paycheck,1000.00,1000.00,123,bar\n"
        result = CsvStandardFamily("Test").parse(content)
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["amount"] == 1000.00

    def test_csv_blank_rows_skipped(self) -> None:
        content = b"Date,Description,Amount\n01/02/2026,Paycheck,1000.00\n\n\n"
        result = CsvStandardFamily("Test").parse(content)
        assert len(result["transactions"]) == 1

    def test_csv_negative_amount_becomes_debit(self) -> None:
        content = b"Date,Description,Amount\n01/02/2026,Purchase,-50.00\n"
        result = CsvStandardFamily("Test").parse(content)
        assert result["transactions"][0]["amount"] == -50.00
        assert result["transactions"][0]["type"] == "debit"


class TestOfxQfxFamilyExtended:
    """Additional OFX family coverage."""

    def test_credit_card_ofx(self) -> None:
        content = (
            b"OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\n\n"
            b"<OFX>"
            b"<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS></SONRS></SIGNONMSGSRSV1>"
            b"<CCMSGSRSV1><STMTTRNRS><TRNUID>1</TRNUID><STMTRS><BANKTRANLIST>"
            b"<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260102</DTPOSTED><TRNAMT>1500.00</TRNAMT><NAME>PAYMENT</NAME></STMTTRN>"
            b"<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260103</DTPOSTED><TRNAMT>-78.45</TRNAMT><NAME>SUPERMARKET</NAME></STMTTRN>"
            b"</BANKTRANLIST></STMTRS></STMTTRNRS></CCMSGSRSV1>"
            b"</OFX>"
        )
        result = OfxQfxFamily("Amex OFX").parse(content)
        assert len(result["transactions"]) == 2
        assert result["transactions"][0]["amount"] == 1500.00
        assert result["transactions"][1]["amount"] == -78.45

    def test_ofx_malformed_date_skipped(self) -> None:
        content = (
            b"OFXHEADER:100\n\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>"
            b"<STMTTRN><DTPOSTED>NOTADATE</DTPOSTED><TRNAMT>100.00</TRNAMT></STMTTRN>"
            b"</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
        )
        result = OfxQfxFamily("Test").parse(content)
        assert result["needs_review"] is True

    def test_ofx_trn_type_check(self) -> None:
        content = (
            b"OFXHEADER:100\n\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>"
            b"<STMTTRN><TRNTYPE>CHECK</TRNTYPE><DTPOSTED>20260102</DTPOSTED><TRNAMT>250.00</TRNAMT><NAME>Check 123</NAME></STMTTRN>"
            b"</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
        )
        result = OfxQfxFamily("Test").parse(content)
        assert result["transactions"][0]["amount"] == -250.00
        assert result["transactions"][0]["type"] == "debit"

    def test_ofx_with_memo_fallback(self) -> None:
        content = (
            b"OFXHEADER:100\n\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>"
            b"<STMTTRN><TRNTYPE>DIRECTDEP</TRNTYPE><DTPOSTED>20260102</DTPOSTED><TRNAMT>500.00</TRNAMT><MEMO>Payroll</MEMO></STMTTRN>"
            b"</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
        )
        result = OfxQfxFamily("Test").parse(content)
        assert result["transactions"][0]["description"] == "Payroll"


class TestPdfTableSimpleFamilyExtended:
    """Additional simple PDF table coverage."""

    def test_date_without_year(self) -> None:
        content = b"Statement Period: 01/01/2026 - 01/31/2026\n01/02 GROCERY -12.34 100.00\n"
        result = PdfTableSimpleFamily("Test").parse(content)
        assert result["transactions"][0]["date"] == "2026-01-02"

    def test_multiple_amounts_on_line(self) -> None:
        content = b"01/02/2026 FEE -5.00 995.00\n"
        result = PdfTableSimpleFamily("Test").parse(content)
        tx = result["transactions"][0]
        assert tx["amount"] == -5.00
        assert tx["balance"] == 995.00

    def test_description_with_extra_spaces(self) -> None:
        content = b"01/02/2026   GROCERY   PURCHASE   -12.34   100.00\n"
        result = PdfTableSimpleFamily("Test").parse(content)
        assert result["transactions"][0]["description"] == "GROCERY   PURCHASE"

    def test_credit_description(self) -> None:
        content = b"01/02/2026 PAYCHECK DEPOSIT 1500.00 1500.00\n"
        result = PdfTableSimpleFamily("Test").parse(content)
        assert result["transactions"][0]["amount"] == 1500.00
        assert result["transactions"][0]["type"] == "credit"


class TestPdfTableMultiFamilyExtended:
    """Additional multi-page PDF table coverage."""

    def test_no_page_markers_falls_back(self) -> None:
        content = b"01/02/2026 A -10.00\n01/03/2026 B -20.00\n"
        result = PdfTableMultiFamily("Test").parse(content)
        assert len(result["transactions"]) == 2

    def test_multiple_page_breaks(self) -> None:
        content = (
            b"Page 1 of 3\n"
            b"01/02/2026 TX1 -10.00 90.00\n"
            b"Page 2 of 3\n"
            b"01/03/2026 TX2 -20.00 70.00\n"
            b"Page 3 of 3\n"
            b"01/04/2026 TX3 -30.00 40.00\n"
        )
        result = PdfTableMultiFamily("Test").parse(content)
        assert len(result["transactions"]) == 3

    def test_ending_balance_stops_parsing(self) -> None:
        content = b"Page 1 of 1\n01/02/2026 A -10.00\nEnding Balance 80.00\n01/03/2026 B -20.00\n"
        result = PdfTableMultiFamily("Test").parse(content)
        assert len(result["transactions"]) == 1


class TestCreditCardPdfFamilyExtended:
    """Additional credit-card PDF coverage."""

    def test_fee_recognized_as_debit(self) -> None:
        content = b"01/02/2026 01/03 ANNUAL FEE -99.00\n"
        result = CreditCardPdfFamily("Amex").parse(content)
        assert result["transactions"][0]["amount"] == -99.00
        assert result["transactions"][0]["type"] == "debit"

    def test_refund_recognized_as_credit(self) -> None:
        content = b"01/02/2026 01/03 REFUND 25.00\n"
        result = CreditCardPdfFamily("Amex").parse(content)
        assert result["transactions"][0]["amount"] == 25.00
        assert result["transactions"][0]["type"] == "credit"

    def test_two_digit_posting_year(self) -> None:
        content = b"Statement Period: 01/01/2026 - 01/31/2026\n01/02/26 01/03/26 SUPERMARKET -45.67\n"
        result = CreditCardPdfFamily("Amex").parse(content)
        assert result["transactions"][0]["date"] == "2026-01-02"
        assert result["transactions"][0]["amount"] == -45.67

    def test_purchase_with_explicit_credit_positive(self) -> None:
        content = b"01/02/2026 01/03 PAYMENT - THANK YOU 500.00\n"
        result = CreditCardPdfFamily("Amex").parse(content)
        assert result["transactions"][0]["amount"] == 500.00
        assert result["transactions"][0]["type"] == "credit"


class TestBrokeragePdfFamilyExtended:
    """Additional brokerage PDF coverage."""

    def test_deposit_positive(self) -> None:
        content = b"01/02/2026 ACH IN 1000.00\n"
        result = BrokeragePdfFamily("Schwab").parse(content)
        assert result["transactions"][0]["amount"] == 1000.00
        assert result["transactions"][0]["type"] == "credit"

    def test_withdrawal_negative(self) -> None:
        content = b"01/02/2026 WIRE OUT -500.00\n"
        result = BrokeragePdfFamily("Schwab").parse(content)
        assert result["transactions"][0]["amount"] == -500.00
        assert result["transactions"][0]["type"] == "debit"

    def test_buy_trade_negative(self) -> None:
        content = b"01/02/2026 BUY SPY -1000.00\n"
        result = BrokeragePdfFamily("Schwab").parse(content)
        assert result["transactions"][0]["amount"] == -1000.00
        assert result["transactions"][0]["type"] == "debit"

    def test_sell_trade_positive(self) -> None:
        content = b"01/02/2026 SALE OF SPY 1500.00\n"
        result = BrokeragePdfFamily("Schwab").parse(content)
        assert result["transactions"][0]["amount"] == 1500.00
        assert result["transactions"][0]["type"] == "credit"

    def test_holdings_and_cash_mixed(self) -> None:
        content = (
            b"Cash Transactions\n"
            b"01/02/2026 DIVIDEND RECEIVED 50.00\n"
            b"Holdings\n"
            b"SYMBOL QTY PRICE\n"
            b"SPY 100 450.00\n"
        )
        result = BrokeragePdfFamily("Schwab").parse(content)
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["amount"] == 50.00


class TestInstitutionRegistryExtended:
    """Additional registry/dispatch coverage."""

    def test_lookup_by_name(self) -> None:
        reg = InstitutionFamilyRegistry()
        entry = reg.lookup("Axos Bank")
        assert entry is not None
        assert entry["family"] == "csv_standard"

    def test_lookup_normalizes_case_and_punctuation(self) -> None:
        reg = InstitutionFamilyRegistry()
        entry = reg.lookup("  axos bank  ")
        assert entry is not None
        assert entry["family"] == "csv_standard"

    def test_unknown_lookup_returns_none(self) -> None:
        reg = InstitutionFamilyRegistry()
        assert reg.lookup("Totally Fake Bank 9999") is None

    def test_detect_csv_by_content(self) -> None:
        content = b"Date,Description,Amount\n01/02/2026,Paycheck,1000.00\n"
        result = detect_institution_family(content, filename="unknown.txt")
        assert result["family"] == "csv_standard"
        assert result["confidence"] == 0.80

    def test_detect_ofx_by_content(self) -> None:
        content = b"OFXHEADER:100\n\n<OFX><BANKMSGSRSV1><STMTTRN></STMTTRN></BANKMSGSRSV1></OFX>"
        result = detect_institution_family(content, filename="unknown.qfx")
        assert result["family"] == "ofx_qfx"
        assert result["confidence"] == 0.80

    def test_detect_credit_card_by_filename(self) -> None:
        content = b"Generic statement text without specific markers\n"
        result = detect_institution_family(content, filename="my_amex_statement.pdf")
        assert result["family"] == "credit_card_pdf"
        assert result["confidence"] == 0.60

    def test_detect_brokerage_by_filename(self) -> None:
        content = b"Generic statement text\n"
        result = detect_institution_family(content, filename="schwab_jan.pdf")
        assert result["family"] == "brokerage_pdf"
        assert result["confidence"] == 0.60

    def test_detect_unknown_defaults_to_pdf_simple(self) -> None:
        content = b"Nothing specific here.\n"
        result = detect_institution_family(content, filename="unknown.pdf")
        assert result["family"] == "pdf_table_simple"
        assert result["confidence"] == 0.30
        assert result["needs_review"] is True

    def test_get_parser_unknown_family_returns_none(self) -> None:
        reg = InstitutionFamilyRegistry()
        assert reg.get_parser("nonexistent", "Test") is None

    def test_institutions_cover_csv_standard(self) -> None:
        reg = InstitutionFamilyRegistry()
        csv_names = [i["name"] for i in reg.all_institutions() if i["family"] == "csv_standard"]
        assert len(csv_names) >= 1

    def test_institutions_cover_pdf_table_simple(self) -> None:
        reg = InstitutionFamilyRegistry()
        names = [i["name"] for i in reg.all_institutions() if i["family"] == "pdf_table_simple"]
        assert len(names) >= 1


class TestFamilyParserSmoke:
    """One-liner smoke tests for every family parser."""

    @pytest.mark.parametrize(
        "parser_cls, content",
        [
            (CsvStandardFamily, b"Date,Description,Amount\n01/02/2026,Paycheck,1000.00\n"),
            (OfxQfxFamily, b"OFXHEADER:100\n\n<OFX><BANKMSGSRSV1></BANKMSGSRSV1></OFX>"),
            (PdfTableSimpleFamily, b"01/02/2026 PAYCHECK 1000.00\n"),
            (PdfTableMultiFamily, b"Page 1 of 1\n01/02/2026 PAYCHECK 1000.00\n"),
            (CreditCardPdfFamily, b"01/02/2026 01/03 SUPERMARKET -78.45\n"),
            (BrokeragePdfFamily, b"Cash Transactions\n01/02/2026 DIVIDEND RECEIVED 50.00\n"),
        ],
    )
    def test_family_parser_returns_result_shape(self, parser_cls: Any, content: bytes) -> None:
        parser = parser_cls("Smoke")
        result = parser.parse(content)
        assert "transactions" in result
        assert "needs_review" in result
        assert "reconciliation" in result

    @pytest.mark.parametrize(
        "parser_cls, content",
        [
            (CsvStandardFamily, b"Date,Description\n01/02/2026,Paycheck\n"),
            (OfxQfxFamily, b"OFXHEADER:100\n\n<OFX></OFX>"),
            (PdfTableSimpleFamily, b"Nothing here\n"),
            (PdfTableMultiFamily, b"Nothing here\n"),
            (CreditCardPdfFamily, b"Nothing here\n"),
            (BrokeragePdfFamily, b"Nothing here\n"),
        ],
    )
    def test_family_parser_empty_returns_needs_review(self, parser_cls: Any, content: bytes) -> None:
        parser = parser_cls("Smoke")
        result = parser.parse(content)
        assert result["needs_review"] is True
        assert result["transactions"] == []


class TestPhase1ParserRegression:
    """Placeholder tests to ensure Phase 1 dedicated parsers still import."""

    def test_phase1_parser_imports(self) -> None:
        from backend.parsers.institution import detect_institution
        from backend.parsers.chase import ChaseParser
        from backend.parsers.wellsfargo import WellsFargoParser
        from backend.parsers.bankofamerica import BankOfAmericaParser

        assert callable(detect_institution)
        assert hasattr(ChaseParser, "can_handle")
        assert hasattr(WellsFargoParser, "can_handle")
        assert hasattr(BankOfAmericaParser, "can_handle")

    def test_phase1_specific_parser_can_handle(self) -> None:
        from backend.parsers.chase import ChaseParser
        assert ChaseParser.can_handle("CHASE BANK\nAccount ending in 1234")
