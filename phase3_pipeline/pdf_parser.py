#!/usr/bin/env python3
"""
PDF Parser for Financial ETL Pipeline.
<<<<<<< HEAD
Supports generic bank statements, Cash App, TD Bank, EdFed CU, Chime.
All dates are output in MM-DD-YYYY format.
"""
import re
from typing import List, Tuple
from pathlib import Path
from decimal import Decimal
from datetime import datetime

from .models import Transaction
from .identity import IdentityService
from .logger import Logger
from .normalization import normalize_amount
from .ocr import extract_text_from_pdf
from .config import OCR_CONFIG
from .alias_utils import normalize_alias

logger = Logger("pdf_parser")

# ----------------------------------------------------------------------
# Helper: normalize date to MM-DD-YYYY
# ----------------------------------------------------------------------
def _normalize_date(date_str: str) -> str:
    """Convert MM/DD/YYYY or MM/DD/YY to MM-DD-YYYY (HomeBank format)."""
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%m-%d-%Y")
        except ValueError:
            continue
    # fallback
    return date_str.replace('/', '-')

# ----------------------------------------------------------------------
# Cash App (with year extraction)
# ----------------------------------------------------------------------
def parse_cash_app_transactions(text: str, institution: str = "Cash App") -> List[Transaction]:
    transactions = []
    lines = text.splitlines()
    year = datetime.now().year
    year_match = re.search(r'([A-Za-z]+)\s+(\d{4})', text)
    if year_match:
        year = int(year_match.group(2))

    current_desc = []
    current_txn = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        date_match = re.match(r'^([A-Za-z]{3}\s+\d{1,2})\s+(.*)', line)
        if date_match:
            if current_txn:
                full_desc = " ".join(current_desc).strip()
                if full_desc:
                    current_txn.description = full_desc
                    current_txn.raw_description = full_desc
                    current_txn.txn_uid = IdentityService.generate(
                        current_txn.date, full_desc, current_txn.amount, institution, len(transactions)
                    )
                    transactions.append(current_txn)

            date_str = date_match.group(1)
            rest = date_match.group(2)
            try:
                date_obj = datetime.strptime(f"{date_str} {year}", "%b %d %Y")
                date = date_obj.strftime("%m-%d-%Y")
            except:
                date = date_str

            amount_match = re.search(r'\$0\.00\s+(.*?)$', rest)
            if amount_match:
                amount_str = amount_match.group(1).strip()
                desc_part = rest[:amount_match.start()].strip()
            else:
                parts = rest.split()
                if not parts:
                    continue
                amount_str = parts[-1]
                desc_part = " ".join(parts[:-1])

            amount_str = amount_str.replace(',', '')
            sign = -1
            if amount_str.startswith('+'):
                sign = 1
                amount_str = amount_str[1:].strip()
            else:
                sign = -1
            numeric_match = re.search(r'(\d+(?:\.\d{2})?)', amount_str)
            if not numeric_match:
                continue
            amount = sign * Decimal(numeric_match.group(1))

            current_txn = Transaction(
                date=date,
                description="",
                raw_description="",
                amount=amount,
                category=None,
                payee=None,
                institution=institution,
                txn_uid="",
            )
            current_desc = [desc_part]
        else:
            if current_txn:
                current_desc.append(line)

    if current_txn:
        full_desc = " ".join(current_desc).strip()
        if full_desc:
            current_txn.description = full_desc
            current_txn.raw_description = full_desc
            current_txn.txn_uid = IdentityService.generate(
                current_txn.date, full_desc, current_txn.amount, institution, len(transactions)
            )
            transactions.append(current_txn)

    logger.info(f"Parsed {len(transactions)} Cash App transactions")
    return transactions

# ----------------------------------------------------------------------
# TD Bank
# ----------------------------------------------------------------------
def parse_td_bank_transactions(text: str, institution: str = "TD Bank") -> List[Transaction]:
    transactions = []
    year = datetime.now().year
    period_match = re.search(r'StatementPeriod:\s+\w+\d{4}-\w+(\d{4})', text)
    if period_match:
        year = int(period_match.group(1))

    lines = text.splitlines()
    pattern = re.compile(r'^(\d{2}/\d{2})\s+([A-Za-z0-9,]+?)\s+([\d,]+\.\d{2})$')
    for line in lines:
        line = line.strip()
        if not line or 'Subtotal:' in line or 'Total' in line:
            continue
        m = pattern.match(line)
        if m:
            date_str = m.group(1)       # MM/DD
            desc = m.group(2).replace(',', ' ')
            amount_str = m.group(3).replace(',', '')
            try:
                amount = Decimal(amount_str)
            except:
                continue
            if any(k in desc.upper() for k in ['DEBIT', 'WITHDRAWAL', 'PAYMENT', 'FEE', 'CHARG']):
                amount = -abs(amount)
            else:
                amount = abs(amount)
            date = f"{date_str.replace('/', '-')}-{year}"
            txn = Transaction(
                date=date,
                description=desc,
                raw_description=line,
                amount=amount,
                category=None,
                payee=None,
                institution=institution,
                txn_uid=IdentityService.generate(date, desc, amount, institution, len(transactions)),
            )
            transactions.append(txn)

    logger.info(f"Parsed {len(transactions)} TD Bank transactions")
    return transactions

# ----------------------------------------------------------------------
# EdFed Checking (with alias normalization)
# ----------------------------------------------------------------------
def parse_edfed_transactions(text: str, institution: str = "EdFed") -> List[Transaction]:
    transactions = []
    lines = text.splitlines()
    year = datetime.now().year
    year_match = re.search(r'([A-Za-z]+)\s+(\d{4})', text[:200])
    if year_match:
        year = int(year_match.group(2))
    
    in_activity = False
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if "ACCOUNT ACTIVITY FOR SHARE DRAFT" in line:
            in_activity = True
            continue
        if not in_activity:
            continue
        
        date_match = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.*)', line)
        if not date_match:
            continue
        
        date_str = date_match.group(1)
        date = _normalize_date(date_str)
        rest = date_match.group(2)
        
        amount = None
        desc_part = rest
        amount_match = re.search(r'(-?\d+(?:,\d{3})*\.\d{2})\s+(\d+(?:,\d{3})*\.\d{2})$', rest)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            try:
                amount = Decimal(amount_str)
            except:
                pass
            desc_part = rest[:amount_match.start()].strip()
        
        # Merge subsequent lines (merchant name)
        full_desc = desc_part
        while i < len(lines):
            next_line = lines[i].strip()
            if not next_line:
                i += 1
                continue
            if re.match(r'^\d{2}/\d{2}/\d{4}', next_line):
                break
            if next_line.startswith(("TYPE:", "ID:", "CO:", "IMPORTANT", "Telephone", "Page", "ACCOUNT ACTIVITY", "SUMMARY")):
                break
            if "Date Posted" in next_line:
                break
            full_desc += " " + next_line
            i += 1
        
        # Clean payee using aliases
        payee = normalize_alias(full_desc)
        if not payee:
            payee = full_desc[:80]
        
        if amount is None:
            amount_match2 = re.search(r'(-?\d+(?:,\d{3})*\.\d{2})', full_desc)
            if amount_match2:
                try:
                    amount = Decimal(amount_match2.group(1).replace(',', ''))
                except:
                    amount = Decimal('0')
            else:
                continue
        
        txn = Transaction(
            date=date,
            description=full_desc,
            raw_description=line,
            amount=amount,
            category=None,
            payee=payee,
            institution=institution,
            txn_uid="",
        )
        transactions.append(txn)
    
    for idx, txn in enumerate(transactions):
        txn.txn_uid = IdentityService.generate(txn.date, txn.description, txn.amount, institution, idx)
    
    logger.info(f"Parsed {len(transactions)} EdFed transactions")
    return transactions

# ----------------------------------------------------------------------
# EdFed Credit Card
# ----------------------------------------------------------------------
def parse_edfed_credit_transactions(text: str, institution: str = "EdFed Credit") -> List[Transaction]:
    transactions = []
    lines = text.splitlines()
    date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})\s+(.*)')
    current_txn = None
    current_desc = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(skip in line for skip in ["TRANSACTIONS", "SUMMARY", "Payment", "Page", "Member", "Account", "Rewards", "VISA", "Credit Limit", "Minimum Payment"]):
            continue
        
        match = date_pattern.match(line)
        if match:
            if current_txn:
                full_desc = " ".join(current_desc).strip()
                if full_desc:
                    current_txn.description = full_desc
                    current_txn.raw_description = full_desc
                    current_txn.txn_uid = IdentityService.generate(
                        current_txn.date, full_desc, current_txn.amount, institution, len(transactions)
                    )
                    transactions.append(current_txn)
            
            date_str = match.group(1)
            date = _normalize_date(date_str)
            rest = match.group(2)
            amount_match = re.search(r'([+-]?\$?\d+(?:,\d{3})*\.\d{2})$', rest)
            if not amount_match:
                continue
            amount_str = amount_match.group(1)
            desc_part = rest[:amount_match.start()].strip()
            amount_clean = amount_str.replace('$', '').replace(',', '')
            try:
                amount = Decimal(amount_clean)
            except:
                continue
            if amount_str.startswith('-') or (amount_str and amount_str[0] == '-'):
                amount = -abs(amount)
            else:
                amount = abs(amount)
            
            current_txn = Transaction(
                date=date,
                description="",
                raw_description="",
                amount=amount,
                category=None,
                payee=None,
                institution=institution,
                txn_uid="",
            )
            current_desc = [desc_part]
        else:
            if current_txn:
                current_desc.append(line)
    
    if current_txn:
        full_desc = " ".join(current_desc).strip()
        if full_desc:
            current_txn.description = full_desc
            current_txn.raw_description = full_desc
            current_txn.txn_uid = IdentityService.generate(
                current_txn.date, full_desc, current_txn.amount, institution, len(transactions)
            )
            transactions.append(current_txn)
    
    logger.info(f"Parsed {len(transactions)} EdFed Credit transactions")
    return transactions

# ----------------------------------------------------------------------
# Chime (with fallback)
# ----------------------------------------------------------------------
def parse_chime_transactions(text: str, institution: str = "Chime") -> List[Transaction]:
    """
    Parse Chime Credit Builder statement.
    Purchases → negative, Payments → positive.
    """
    transactions = []
    lines = text.splitlines()
    
    # Locate transactions and payments sections
    trans_header = -1
    payments_header = -1
    for i, line in enumerate(lines):
        if "TRANSACTION DATE" in line and "AMOUNT" in line:
            trans_header = i
        if line.strip() == "Payments" and i > trans_header:
            payments_header = i
            break
    
    # Process Transactions section (purchases, transfers)
    if trans_header != -1:
        end_idx = payments_header if payments_header != -1 else len(lines)
        for line in lines[trans_header+1:end_idx]:
            line = line.strip()
            if not line or line.startswith("Page"):
                continue
            if not re.match(r'^\d{1,2}/\d{1,2}/\d{4}', line):
                continue
            amount_match = re.search(r'(-?\$?\d+(?:,\d{3})*\.\d{2})', line)
            if not amount_match:
                continue
            amount_str = amount_match.group(1)
            amount_clean = amount_str.replace('$', '').replace(',', '')
            try:
                amount = Decimal(amount_clean)
            except:
                continue
            # For Chime, purchases in the Transactions section are positive but represent debits
            amount = -abs(amount)
            desc_part = line[:amount_match.start()].strip()
            date_parts = desc_part.split(maxsplit=1)
            desc = date_parts[1].strip() if len(date_parts) > 1 else ""
            date_str = line.split()[0]
            date = _normalize_date(date_str)
            txn = Transaction(
                date=date,
                description=desc,
                raw_description=line,
                amount=amount,
                category=None,
                payee=normalize_alias(desc),
                institution=institution,
                txn_uid=IdentityService.generate(date, desc, amount, institution, len(transactions)),
            )
            transactions.append(txn)
    
    # Process Payments section (credits)
    if payments_header != -1:
        for line in lines[payments_header+1:]:
            line = line.strip()
            if not line or line.startswith("Page") or "TOTAL FOR THIS PERIOD" in line:
                continue
            if not re.match(r'^\d{1,2}/\d{1,2}/\d{4}', line):
                continue
            amount_match = re.search(r'(-?\$?\d+(?:,\d{3})*\.\d{2})', line)
            if not amount_match:
                continue
            amount_str = amount_match.group(1)
            amount_clean = amount_str.replace('$', '').replace(',', '')
            try:
                amount = Decimal(amount_clean)
            except:
                continue
            # Payments are credits → positive
            amount = abs(amount)
            desc_part = line[:amount_match.start()].strip()
            date_parts = desc_part.split(maxsplit=1)
            desc = date_parts[1].strip() if len(date_parts) > 1 else ""
            date_str = line.split()[0]
            date = _normalize_date(date_str)
            txn = Transaction(
                date=date,
                description=desc,
                raw_description=line,
                amount=amount,
                category=None,
                payee=normalize_alias(desc),
                institution=institution,
                txn_uid=IdentityService.generate(date, desc, amount, institution, len(transactions)),
            )
            transactions.append(txn)
    
    # Deduplicate by date+description+amount
    seen = set()
    unique = []
    for txn in transactions:
        key = (txn.date, txn.description, txn.amount)
        if key not in seen:
            seen.add(key)
            unique.append(txn)
    if len(unique) != len(transactions):
        logger.warning(f"Removed {len(transactions)-len(unique)} duplicate Chime transactions")
    
    logger.info(f"Parsed {len(unique)} Chime transactions")
    return unique

# ----------------------------------------------------------------------
# Advanced Generic Parser (robust amounts, CR/DR, parentheses)
# ----------------------------------------------------------------------
def parse_generic_advanced(text: str, institution: str = "unknown") -> List[Transaction]:
    transactions = []
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Extract date at start
        date_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4})\s+(.*)', line)
        if not date_match:
            continue
        date_str = date_match.group(1)
        remaining = date_match.group(2)

        # Extract amount from end (supports parentheses, +/-, $)
        amount_match = re.search(r'([\(\)\+\-\$]?[\d,]+\.\d{2}[\)]?)$', remaining)
        if not amount_match:
            continue
        amount_str = amount_match.group(1)
        # Remove parentheses (negative)
        if amount_str.startswith('(') and amount_str.endswith(')'):
            amount_str = '-' + amount_str[1:-1]
        amount_str = amount_str.replace('$', '').replace(',', '')

        # Handle CR/DR markers (word boundaries)
        if re.search(r'\bCR\b', line, re.IGNORECASE):
            amount_str = '+' + amount_str.lstrip('+-')
        elif re.search(r'\bDR\b', line, re.IGNORECASE):
            amount_str = '-' + amount_str.lstrip('+-')

        amount = normalize_amount(amount_str)
        if amount is None:
            continue

        # Description is everything before the amount
        desc = remaining[:amount_match.start()].strip()
        date = _normalize_date(date_str)

        txn = Transaction(
            date=date,
            description=desc,
            raw_description=line,
            amount=amount,
            category=None,
            payee=desc[:80],  # will be normalized later by categorizer
            institution=institution,
            txn_uid=IdentityService.generate(date, desc, amount, institution, len(transactions)),
        )
        transactions.append(txn)

    if transactions:
        logger.info(f"Parsed {len(transactions)} transactions using advanced generic parser")
        return transactions
    return parse_generic_transactions(text, institution)

# ----------------------------------------------------------------------
# Original Generic Fallback
# ----------------------------------------------------------------------
def parse_generic_transactions(text: str, institution: str = "unknown") -> List[Transaction]:
    transactions = []
    lines = text.splitlines()
    patterns = [
        r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(.*?)\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'(\d_{1,2}/\d_{1,2}/\d_{2,4})\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)\s+(.*)',
        r'(\d_{1,2}/\d_{1,2}/\d_{2,4})\s+Withdrawal.*?\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)\s+(.*)',
        r'(\d_{1,2}/\d_{1,2}/\d_{2,4})\s+Deposit.*?\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)\s+(.*)',
    ]
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        matched = False
        for pat in patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                groups = m.groups()
                date_str = groups[0]
                date = _normalize_date(date_str)
                amount_str = None
                desc = None
                for g in groups[1:]:
                    if re.search(r'[\$\-]?\d+(?:,\d{3})*(?:\.\d{2})?', g):
                        amount_str = g
                    elif len(g) > 2:
                        desc = g
                if amount_str and desc:
                    amount = normalize_amount(amount_str)
                    if amount is not None:
                        txn = Transaction(
                            date=date,
                            description=desc,
                            raw_description=line,
                            amount=amount,
                            category=None,
                            payee=None,
                            institution=institution,
                            txn_uid=IdentityService.generate(date, desc, amount, institution, len(transactions)),
                        )
                        transactions.append(txn)
                        matched = True
                        break
        if not matched and len(line) > 10:
            logger.debug(f"Unmatched line: {line[:80]}")
    logger.info(f"Parsed {len(transactions)} transactions using generic parser")
    return transactions

# ----------------------------------------------------------------------
# Institution detection
# ----------------------------------------------------------------------
def detect_institution(text: str) -> str:
    text_lower = text.lower()
    if "share draft" in text_lower or "educational federal" in text_lower:
        return "EdFed"
    if "cash app" in text_lower and any(m in text_lower for m in ["to ", "from ", "cash app payment", "cash app card"]):
        return "Cash App"
    if "chime" in text_lower:
        return "Chime"
    if "td bank" in text_lower or "tdbusiness" in text_lower:
        return "TD Bank"
    if "bank of america" in text_lower:
        return "Bank of America"
    if "chase" in text_lower:
        return "Chase"
    if "wells fargo" in text_lower:
        return "Wells Fargo"
    return "unknown"

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def pdf_to_transactions(pdf_path: Path, profile: str = "personal") -> Tuple[List[Transaction], str]:
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return [], ""
    prefer_digital = OCR_CONFIG.get("prefer_digital", True)
    raw_text = extract_text_from_pdf(pdf_path, prefer_digital=prefer_digital)
    if not raw_text:
        logger.error(f"No text extracted from {pdf_path}")
        return [], ""
    
    institution = detect_institution(raw_text)
    logger.info(f"Detected institution: {institution}")
    
    # Special case: EdFed Credit Card
    if "REWARDS VISA" in raw_text or "Credit Card Statement" in raw_text:
        transactions = parse_edfed_credit_transactions(raw_text, "EdFed Credit")
    elif institution == "Cash App":
        transactions = parse_cash_app_transactions(raw_text, institution)
        if not transactions:
            logger.warning("Cash App parser returned 0 transactions, falling back to generic")
            transactions = parse_generic_advanced(raw_text, institution)
    elif institution == "Chime":
        transactions = parse_chime_transactions(raw_text, institution)
        if not transactions:
            logger.warning("Chime parser returned 0 transactions, falling back to generic")
            transactions = parse_generic_advanced(raw_text, institution)
    elif institution == "TD Bank":
        transactions = parse_td_bank_transactions(raw_text, institution)
        if not transactions:
            logger.warning("TD Bank parser returned 0 transactions, falling back to generic")
            transactions = parse_generic_advanced(raw_text, institution)
    elif institution == "EdFed":
        transactions = parse_edfed_transactions(raw_text, institution)
        if not transactions:
            logger.warning("EdFed parser returned 0 transactions, falling back to generic")
            transactions = parse_generic_advanced(raw_text, institution)
    else:
        transactions = parse_generic_advanced(raw_text, institution)

    # Deduplicate by txn_uid
    seen = set()
    unique = []
    for txn in transactions:
        if txn.txn_uid not in seen:
            seen.add(txn.txn_uid)
            unique.append(txn)
    if len(unique) != len(transactions):
        logger.warning(f"Removed {len(transactions)-len(unique)} duplicate transactions")
=======

This module is now a thin backward-compatible wrapper around the unified
backend/parsers package. The canonical parsing logic lives in
backend/parsers.generic_pdf (GenericPDFParser) and the phase3
phase3_pipeline/parsers plugin registry.
"""
from typing import List, Tuple
from pathlib import Path

from .models import Transaction
from .ocr import extract_text_from_pdf
from .config import OCR_CONFIG
import sys
from pathlib import Path

# Allow imports from the project root so backend.parsers is reachable.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.parsers import (
    parse_pdf_to_dict,
    parse_pdf_to_transactions,
    detect_institution,
)
from .parsers import get_parser


# Re-export institution detection so downstream callers keep working.
__all__ = [
    "pdf_to_transactions",
    "detect_institution",
]


def pdf_to_transactions(pdf_path: Path, profile: str = "personal") -> Tuple[List[Transaction], str]:
    """Backward-compatible pipeline entry point."""
    if not pdf_path.exists():
        return [], ""

    prefer_digital = OCR_CONFIG.get("prefer_digital", True)
    raw_text = extract_text_from_pdf(pdf_path, prefer_digital=prefer_digital)
    if not raw_text:
        return [], ""

    institution = detect_institution(raw_text)

    # Special case: EdFed credit card is not covered by the plugin registry
    # but the unified generic parser may still find transactions.
    if "REWARDS VISA" in raw_text or "Credit Card Statement" in raw_text:
        institution = "EdFed Credit"

    # Try the phase3 plugin parser registry first for institution-specific logic.
    parser = get_parser(raw_text)
    parsed_institution = getattr(parser, "institution_name", institution)
    plugin_transactions = parser.parse(raw_text)

    # If the plugin registry returned nothing, fall back to the unified backend parser.
    if not plugin_transactions:
        tx_dicts = parse_pdf_to_transactions(pdf_path, institution=institution)
        plugin_transactions = [
            Transaction(
                date=tx.get("date", ""),
                description=tx.get("description", ""),
                raw_description=tx.get("description", ""),
                amount=tx.get("amount") or 0,
                category=None,
                payee=tx.get("description", "")[:80],
                institution=institution or parsed_institution,
                txn_uid="",
            )
            for tx in tx_dicts
        ]

    # Ensure every transaction has a stable uid.
    for idx, txn in enumerate(plugin_transactions):
        if not txn.txn_uid:
            from .identity import IdentityService
            txn.txn_uid = IdentityService.generate(
                txn.date, txn.description, txn.amount, txn.institution, idx
            )

    # Deduplicate by txn_uid.
    seen = set()
    unique = []
    for txn in plugin_transactions:
        if txn.txn_uid not in seen:
            seen.add(txn.txn_uid)
            unique.append(txn)

>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    return unique, raw_text
