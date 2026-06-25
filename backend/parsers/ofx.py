"""Dependency-free OFX/QFX statement parser for TaxFlow Pro v3.11.

Supports both OFX 1.x SGML-style and OFX 2.x XML-style documents, plus the
QFX variant produced by Quicken/QuickBooks. Extracts account metadata,
statement period, and transactions with FITID-based deduplication keys.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class OFXParseError(Exception):
    """Raised when an OFX/QFX document cannot be parsed."""


@dataclass
class OFXAccount:
    bank_id: Optional[str] = None
    account_id: str = ""
    account_type: str = "checking"
    currency: str = "USD"


@dataclass
class OFXTransaction:
    fitid: str
    date: date
    amount: Decimal
    description: str
    check_number: Optional[str] = None


@dataclass
class OFXStatement:
    account: OFXAccount
    transactions: list[OFXTransaction]
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None


def _strip_tags(text: str) -> str:
    """Remove newline + tag clutter; normalize whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _parse_ofx_date(value: Optional[str]) -> Optional[date]:
    """Parse OFX datetime strings like 20260102120000 or 2026-01-02."""
    if not value:
        return None
    value = value.strip()
    # OFX datetimes: YYYYMMDDHHMMSS[.sss][+/-TZ]
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", value)
    if m:
        year, month, day = m.groups()
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None
    # ISO fallback
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_amount(value: Optional[str]) -> Optional[Decimal]:
    if not value:
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except Exception:
        return None


def _extract_text_block(data: str, start_tag: str, end_tag: str) -> Optional[str]:
    start = data.find(f"<{start_tag}>")
    if start == -1:
        return None
    start += len(start_tag) + 2
    end = data.find(f"</{end_tag}>", start)
    if end == -1:
        # OFX 1.x uses close tags without leading slash sometimes; try plain tag
        end = data.find(f"<{end_tag}>", start)
    if end == -1:
        return None
    return data[start:end].strip()


def _extract_tag(data: str, tag: str) -> Optional[str]:
    """Extract the first occurrence of <TAG>value</TAG> or <TAG>value."""
    patterns = [
        rf"<{tag}>([^<]+)</{tag}>",
        rf"<{tag}>([^<\n]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, data, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _coalesce(*values: Optional[str]) -> str:
    for v in values:
        if v:
            return v.strip()
    return ""


def _parse_bank_account(data: str) -> OFXAccount:
    """Parse <BANKACCTFROM> block."""
    block = _extract_text_block(data, "BANKACCTFROM", "BANKACCTFROM")
    if block is None:
        return OFXAccount(account_type="checking")
    return OFXAccount(
        bank_id=_extract_tag(block, "BANKID"),
        account_id=_coalesce(_extract_tag(block, "ACCTID"), _extract_tag(block, "ACCOUNTID")),
        account_type=_coalesce(_extract_tag(block, "ACCTTYPE"), "checking").lower(),
        currency=_coalesce(_extract_tag(block, "CURDEF"), "USD"),
    )


def _parse_credit_card_account(data: str) -> OFXAccount:
    """Parse <CCACCTFROM> block."""
    block = _extract_text_block(data, "CCACCTFROM", "CCACCTFROM")
    if block is None:
        return None  # type: ignore[return-value]
    return OFXAccount(
        bank_id=_extract_tag(block, "BANKID"),
        account_id=_coalesce(_extract_tag(block, "ACCTID"), _extract_tag(block, "ACCOUNTID")),
        account_type="credit_card",
        currency=_coalesce(_extract_tag(block, "CURDEF"), "USD"),
    )


def _parse_transactions(data: str) -> list[OFXTransaction]:
    """Parse all <STMTTRN> entries in the document."""
    txns: list[OFXTransaction] = []
    # Split by STMTTRN opening tags
    parts = re.split(r"<STMTTRN>", data, flags=re.IGNORECASE)
    for part in parts[1:]:
        # Determine end: next opening of a sibling/closing block
        end = re.search(r"</STMTTRN>|(?=<STMTTRN>|<BANKTRANLIST>|</BANKTRANLIST>|</CCSTMTRS>|</BANKSTMTRS>|</STMTTRNRS>)", part, flags=re.IGNORECASE)
        block = part[:end.start()] if end else part

        amount = _parse_amount(_extract_tag(block, "TRNAMT"))
        if amount is None:
            continue
        fitid = _coalesce(_extract_tag(block, "FITID"), _extract_tag(block, "TRANSACTIONID"))
        if not fitid:
            # Generate deterministic fallback for tests, but real OFX should have FITID.
            fitid = f"nofitid-{hash(block) & 0xFFFFFFFF}"
        dt_posted = _parse_ofx_date(_extract_tag(block, "DTPOSTED"))
        if dt_posted is None:
            dt_user = _parse_ofx_date(_extract_tag(block, "DTUSER"))
            dt_posted = dt_user if dt_user else date(1970, 1, 1)

        description = _coalesce(
            _extract_tag(block, "NAME"),
            _extract_tag(block, "MEMO"),
            _extract_tag(block, "PAYEE"),
        )
        check_num = _extract_tag(block, "CHECKNUM") or _extract_tag(block, "CHECKNUM")

        txns.append(
            OFXTransaction(
                fitid=fitid,
                date=dt_posted,
                amount=amount,
                description=description,
                check_number=check_num,
            )
        )
    return txns


def _parse_statement_period(data: str) -> tuple[Optional[date], Optional[date]]:
    """Parse <BANKTRANLIST> DTSTART / DTEND."""
    block = _extract_text_block(data, "BANKTRANLIST", "BANKTRANLIST")
    if block is None:
        return None, None
    return _parse_ofx_date(_extract_tag(block, "DTSTART")), _parse_ofx_date(_extract_tag(block, "DTEND"))


def _parse_balance(data: str, tag: str) -> Optional[Decimal]:
    block = _extract_text_block(data, "LEDGERBAL", "LEDGERBAL") or _extract_text_block(data, "AVAILBAL", "AVAILBAL")
    if block is None:
        return None
    return _parse_amount(_extract_tag(block, tag))


def parse_ofx(data: bytes) -> OFXStatement:
    """Parse raw OFX/QFX bytes into an OFXStatement."""
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception as exc:
        raise OFXParseError(f"Could not decode OFX bytes: {exc}") from exc

    if "<OFX>" not in text.upper():
        raise OFXParseError("Missing <OFX> root tag")

    account = _parse_credit_card_account(text) or _parse_bank_account(text)
    if not account.account_id:
        # Fallback for files where the account block is missing or unusual
        account.account_id = _extract_tag(text, "ACCTID") or ""

    period_start, period_end = _parse_statement_period(text)
    if period_start is None:
        # Try global dates
        period_start = _parse_ofx_date(_extract_tag(text, "DTSTART"))
        period_end = _parse_ofx_date(_extract_tag(text, "DTEND"))

    return OFXStatement(
        account=account,
        transactions=_parse_transactions(text),
        period_start=period_start,
        period_end=period_end,
        opening_balance=None,
        closing_balance=_parse_balance(text, "BALAMT"),
    )
