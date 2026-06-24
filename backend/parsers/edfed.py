"""Educational Federal Credit Union checking and credit-card parser."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .parser_base import (
    build_parse_result,
    extract_amounts,
    infer_year,
    make_tx,
    normalize_signed_amount,
    parse_date_us,
)


def _looks_like_credit(text: str) -> bool:
    tl = text.lower()
    return any(
        marker in tl
        for marker in [
            "edfed rewards visa",
            "edfed credit card",
            "educational federal credit union credit",
            "rewards visa",
            "visa",
        ]
    )


def _extract_balances(text: str) -> Tuple[Optional[float], Optional[float]]:
    opening = None
    closing = None
    for m in re.finditer(r'(?:previous|beginning|opening)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        try:
            opening = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    for m in re.finditer(r'(?:new|closing|ending|current)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        try:
            closing = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    return opening, closing


def _parse_share_draft(text: str) -> List[Dict[str, Any]]:
    transactions: List[Dict[str, Any]] = []
    seen: set = set()
    lines = text.splitlines()
    in_activity = False
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if "account activity for share draft" in line.lower():
            in_activity = True
            continue
        if not in_activity:
            continue

        m = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.*)$', line)
        if not m:
            continue
        date = parse_date_us(m.group(1))
        rest = m.group(2)

        # Try to grab amount + trailing balance.
        amount_match = re.search(r'(-?\d+(?:,\d{3})*\.\d{2})\s+(\d+(?:,\d{3})*\.\d{2})$', rest)
        desc = rest
        amount = None
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
            except ValueError:
                amount = None
            desc = rest[:amount_match.start()].strip()
        if amount is None:
            amts = extract_amounts(rest)
            if amts:
                amount = amts[-1][2]
                desc = rest[:amts[-1][0]].strip() or desc

        if amount is None:
            continue

        # Merge continuation lines that aren't new dates or markers.
        full_desc = desc
        while i < len(lines):
            next_line = lines[i].strip()
            if not next_line:
                i += 1
                continue
            if re.match(r'^\d{2}/\d{2}/\d{4}', next_line):
                break
            if next_line.lower().startswith(("type:", "id:", "co:", "important", "telephone", "page", "account activity", "summary", "date posted")):
                break
            full_desc += " " + next_line
            i += 1

        is_debit = any(k in full_desc.lower() for k in ["withdrawal", "debit", "transfer to", "fee", "check"])
        amount = normalize_signed_amount(amount, is_debit)

        key = (date, full_desc, amount)
        if key in seen:
            continue
        seen.add(key)
        transactions.append(make_tx(date, full_desc, amount))

    return transactions


def _parse_credit(text: str) -> List[Dict[str, Any]]:
    transactions: List[Dict[str, Any]] = []
    seen: set = set()
    desc_lines: List[str] = []
    current: Optional[Dict[str, Any]] = None

    for line in text.splitlines():
        line = line.strip()
        if not line or any(skip in line.lower() for skip in ["transactions", "summary", "payment", "page", "member", "account", "rewards", "visa", "credit limit", "minimum payment"]):
            continue

        m = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.*)$', line)
        if m:
            if current and desc_lines:
                desc = " ".join(desc_lines).strip()
                current["description"] = desc
                current["raw_description"] = desc
                key = (current["date"], desc, current["amount"])
                if key not in seen:
                    seen.add(key)
                    transactions.append(current)

            date = parse_date_us(m.group(1))
            rest = m.group(2)
            amts = extract_amounts(rest)
            if not amts:
                current = None
                desc_lines = []
                continue
            amount_val = amts[-1][2]
            desc_part = rest[:amts[-1][0]].strip()
            is_debit = not ("payment" in desc_part.lower() or "credit" in desc_part.lower() or amount_val < 0)
            amount = normalize_signed_amount(abs(amount_val), is_debit)
            current = make_tx(date or "", desc_part, amount)
            desc_lines = []
        elif current:
            desc_lines.append(line)

    if current and desc_lines:
        desc = " ".join(desc_lines).strip()
        current["description"] = desc
        current["raw_description"] = desc
        key = (current["date"], desc, current["amount"])
        if key not in seen:
            seen.add(key)
            transactions.append(current)

    return transactions


class EdFedParser:
    institution_name = "EdFed"

    @classmethod
    def can_handle(cls, text: str) -> bool:
        tl = text.lower()
        return any(marker in tl for marker in ["educational federal", "edfed"])

    @classmethod
    def parse(cls, pdf_path: str, raw_text: str) -> Dict[str, Any]:
        opening, closing = _extract_balances(raw_text)
        if _looks_like_credit(raw_text):
            transactions = _parse_credit(raw_text)
        else:
            transactions = _parse_share_draft(raw_text)
        return build_parse_result(
            transactions,
            cls.institution_name,
            opening_balance=opening,
            closing_balance=closing,
            needs_review=len(transactions) == 0,
        )


def parse_edfed_pdf(pdf_path: str, raw_text: str) -> Dict[str, Any]:
    return EdFedParser.parse(pdf_path, raw_text)
