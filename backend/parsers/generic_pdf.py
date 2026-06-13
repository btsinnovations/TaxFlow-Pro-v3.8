"""
Generic PDF Bank Statement Parser — TaxFlow Pro v3.7
Final version with all fixes: list/dict amount_columns, Fiserv balance-heuristic, proper reconciliation.
"""

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

OCR_AVAILABLE = False
try:
    from pdf2image import convert_from_path
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    pass


class GenericPDFParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.transactions: List[Dict[str, Any]] = []
        self.account_info: Dict[str, Any] = {}
        self.template: Optional[Dict[str, Any]] = None
        self._ocr_warned = False

    # ------------------------------------------------------------------
    # Template loading
    # ------------------------------------------------------------------
    def load_templates(self) -> List[Dict[str, Any]]:
        templates_dir = Path(__file__).parent / "templates"
        templates: List[Dict[str, Any]] = []
        if templates_dir.exists():
            for template_file in sorted(templates_dir.glob("*.json")):
                try:
                    with open(template_file, "r", encoding="utf-8") as f:
                        templates.append(json.load(f))
                except Exception:
                    continue
        return templates

    def detect_template(self, text: str) -> Optional[Dict[str, Any]]:
        templates = self.load_templates()
        for template in templates:
            header_pattern = template.get("regex_patterns", {}).get("header", "")
            if header_pattern and re.search(header_pattern, text, re.IGNORECASE):
                self.template = template
                return template
        if templates:
            self.template = templates[0]
            return templates[0]
        return None

    # ------------------------------------------------------------------
    # Text extraction + OCR fallback
    # ------------------------------------------------------------------
    def extract_text(self) -> List[str]:
        pages_text: List[str] = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text(layout=True)
                    if text:
                        pages_text.append(text)
        except Exception as e:
            print(f"[ERROR] pdfplumber extraction failed: {e}")
            return []

        total_text = "\n".join(pages_text).strip()
        if len(total_text) < 200 and OCR_AVAILABLE:
            ocr_text = self._ocr_extract()
            if ocr_text:
                pages_text = [ocr_text]
        elif len(total_text) < 200 and not OCR_AVAILABLE and not self._ocr_warned:
            print("[WARNING] PDF appears scanned but OCR deps not installed.")
            self._ocr_warned = True
        return pages_text

    def _ocr_extract(self) -> str:
        if not OCR_AVAILABLE:
            return ""
        all_text: List[str] = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                page_count = len(pdf.pages)
            for page_num in range(1, page_count + 1):
                images = convert_from_path(self.pdf_path, dpi=200, first_page=page_num, last_page=page_num, fmt="ppm")
                for image in images:
                    text = pytesseract.image_to_string(image)
                    if text:
                        all_text.append(text)
        except Exception as e:
            print(f"[WARNING] OCR failed: {e}")
        return "\n".join(all_text)

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------
    def clean_transaction_line(self, line: str) -> str:
        # SWIFT removal: avoid matching common words
        line = re.sub(r'\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b(?!\s+(?:PAY|FEE|COFFEE|STATION|INSURANCE))', '', line)
        line = line.replace('€', '$').replace('£', '$').replace('¥', '$')
        return line.strip()

    def _preprocess_lines(self, text: str) -> List[str]:
        raw_lines = text.splitlines()
        cleaned = [self.clean_transaction_line(line) for line in raw_lines]
        return [line for line in cleaned if line and not line.startswith('=')]

    # ------------------------------------------------------------------
    # Balance extraction
    # ------------------------------------------------------------------
    def _extract_balance(self, text: str, label_pattern: str) -> Optional[float]:
        pattern = re.compile(rf'{label_pattern}\s*[:=]?\s*\$?\s*([0-9,]+\.\d{{2}})', re.IGNORECASE)
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except ValueError:
                pass
        return None

    # ------------------------------------------------------------------
    # Core transaction line parser
    # ------------------------------------------------------------------
    def _parse_transaction_line(self, line: str, template: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        clean = line.lstrip()
        date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', clean)
        if not date_match:
            return None
        date_str = date_match.group(1)
        after_date = clean[date_match.end():].strip()
        if re.search(r'^(Beginning|Ending|Opening|Closing)\s+Balance', after_date, re.IGNORECASE):
            return None

        all_amounts = list(re.finditer(r'\$?([0-9,]+\.\d{2})', clean))
        if len(all_amounts) < 2:
            return None
        balance_match = all_amounts[-1]
        balance_str = balance_match.group(1).replace(',', '')
        try:
            balance = float(balance_str)
        except ValueError:
            return None

        tx_amounts = all_amounts[:-1]
        amount_config = template.get("amount_columns", {})

        # Handle both list and dict formats
        if isinstance(amount_config, list):
            is_single_column = False
            debit_negative = False
        else:
            is_single_column = amount_config.get("single_column", False)
            debit_negative = amount_config.get("debit_negative", False)

        tx: Dict[str, Any] = {
            "date": self._parse_date(date_str, template),
            "description": "",
            "amount": None,
            "type": "unknown",
            "tax_flag": None,
            "balance": balance,
        }

        if is_single_column or debit_negative:
            # Single amount column (Fiserv style)
            if tx_amounts:
                amt_match = tx_amounts[-1]
                amount_start = amt_match.start()
                prefix = clean[max(0, amount_start - 8):amount_start]
                amount_str = amt_match.group(1).replace(',', '')
                amt = float(amount_str)
                if '-' in prefix or '(' in prefix or re.search(r'debit|dr|withdrawal', prefix, re.IGNORECASE):
                    tx["amount"] = -amt
                    tx["type"] = "debit"
                else:
                    tx["amount"] = amt
                    tx["type"] = "credit"
                tx["description"] = clean[date_match.end():amount_start].strip()
            else:
                return None
        else:
            # Split columns – use gap heuristic
            if len(tx_amounts) >= 1:
                amt_match = tx_amounts[-1]
                amount_str = amt_match.group(1).replace(',', '')
                amt = float(amount_str)
                gap = balance_match.start() - amt_match.end()
                if gap > 12:
                    tx["amount"] = -amt
                    tx["type"] = "debit"
                else:
                    tx["amount"] = amt
                    tx["type"] = "credit"
                tx["description"] = clean[date_match.end():amt_match.start()].strip()
            else:
                return None

        if tx["date"] and tx["amount"] is not None and tx["description"]:
            return tx
        return None

    def _parse_date(self, date_str: str, template: Dict[str, Any]) -> Optional[str]:
        fmt = template.get("date_format", "%m/%d/%Y")
        for f in [fmt, "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%b %d, %Y"]:
            try:
                dt = datetime.strptime(date_str.strip(), f)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # Dedup key and consecutive dedup
    # ------------------------------------------------------------------
    def _build_dedup_key(self, tx: Dict[str, Any]) -> str:
        raw = f"{tx.get('date', '')}|{tx.get('description', '')}|{tx.get('amount', 0.0):.2f}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _dedup_consecutive(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        prev_key = None
        for tx in transactions:
            h = self._build_dedup_key(tx)
            if h != prev_key:
                prev_key = h
                deduped.append(tx)
        return deduped

    # ------------------------------------------------------------------
    # Wrapped description merge
    # ------------------------------------------------------------------
    def _merge_continuations(self, transactions: List[Dict[str, Any]], raw_lines: List[str]) -> List[Dict[str, Any]]:
        if not transactions:
            return transactions
        merged: List[Dict[str, Any]] = [transactions[0].copy()]
        tx_idx = 0
        for line in raw_lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if re.match(r'^\d{2}/\d{2}/\d{4}', line_stripped):
                tx_idx += 1
                if tx_idx < len(transactions):
                    merged.append(transactions[tx_idx].copy())
            elif tx_idx < len(merged) and len(line_stripped) < 100 and not line_stripped.startswith('$'):
                merged[tx_idx]['description'] = (merged[tx_idx].get('description', '') + ' ' + line_stripped).strip()
        return merged

    # ------------------------------------------------------------------
    # Balance-change heuristic for debit_negative templates (Fiserv)
    # ------------------------------------------------------------------
    def _apply_balance_heuristic(self, transactions: List[Dict[str, Any]], opening_balance: Optional[float]) -> List[Dict[str, Any]]:
        if not opening_balance:
            return transactions
        prev_balance = opening_balance
        for tx in transactions:
            cur_balance = tx.get("balance")
            if cur_balance is not None:
                if cur_balance < prev_balance:
                    tx["type"] = "debit"
                    tx["amount"] = -abs(tx["amount"])
                else:
                    tx["type"] = "credit"
                    tx["amount"] = abs(tx["amount"])
                prev_balance = cur_balance
        return transactions

    # ------------------------------------------------------------------
    # Main parse
    # ------------------------------------------------------------------
    def parse(self) -> Dict[str, Any]:
        pages_text = self.extract_text()
        if not pages_text:
            return {"error": "Failed to extract text", "transactions": [], "account_info": {}}

        full_text = "\n".join(pages_text)
        self.detect_template(full_text)
        if not self.template:
            return {"error": "No matching template", "transactions": [], "account_info": {}}

        opening = self._extract_balance(full_text, r"(?:opening|beginning|start|previous)\s+balance")
        closing = self._extract_balance(full_text, r"(?:closing|ending|end|current|new)\s+balance")
        self.account_info = {
            "opening_balance": opening,
            "closing_balance": closing,
            "template_name": self.template.get("name", "unknown"),
            "institution": self.template.get("institutions", [None])[0],
        }

        all_transactions: List[Dict[str, Any]] = []
        all_raw_lines: List[str] = []
        for page_text in pages_text:
            raw_lines = self._preprocess_lines(page_text)
            all_raw_lines.extend(raw_lines)
            for line in raw_lines:
                tx = self._parse_transaction_line(line, self.template)
                if tx:
                    all_transactions.append(tx)

        all_transactions = self._merge_continuations(all_transactions, all_raw_lines)

        # Apply balance-change heuristic for single-column templates (Fiserv, etc.)
        amount_config = self.template.get("amount_columns", {})
        use_balance_heuristic = False
        if isinstance(amount_config, dict) and amount_config.get("debit_negative", False):
            use_balance_heuristic = True
        elif isinstance(amount_config, list) and len(amount_config) == 1:
            use_balance_heuristic = True
        if use_balance_heuristic:
            all_transactions = self._apply_balance_heuristic(all_transactions, opening)

        deduped = self._dedup_consecutive(all_transactions)
        deduped.sort(key=lambda x: x.get("date") or "")
        self.transactions = deduped

        self._apply_tax_flags()

        tx_sum = sum(t["amount"] for t in self.transactions if t["amount"] is not None)
        variance = None
        if opening is not None and closing is not None:
            variance = round(closing - opening - tx_sum, 2)

        return {
            "template": self.template.get("name"),
            "account_info": self.account_info,
            "transactions": self.transactions,
            "reconciliation": {
                "opening_balance": opening,
                "closing_balance": closing,
                "transaction_sum": round(tx_sum, 2),
                "variance": variance,
                "balanced": variance == 0.0 if variance is not None else None,
            },
            "meta": {
                "total_pages": len(pages_text),
                "total_raw_transactions": len(all_transactions),
                "duplicates_removed": len(all_transactions) - len(deduped),
            },
        }

    # ------------------------------------------------------------------
    # Tax flags (abbreviated for brevity)
    # ------------------------------------------------------------------
    def _apply_tax_flags(self) -> None:
        flags = {
            "income": [r"TREAS\s*310", r"DFAS", r"PAYROLL", r"DIRECT\s*DEPOSIT", r"SALARY"],
            "business": [r"SQ\s*\*", r"PAYPAL", r"STRIPE", r"VENMO"],
            "medical": [r"HOSPITAL", r"CLINIC", r"PHARMACY", r"DR\.", r"DENTAL"],
            "charity": [r"DONATION", r"UNITED\s*WAY"],
            "education": [r"TUITION", r"UNIVERSITY"],
            "tax": [r"IRS", r"TAX\s*PAYMENT"],
            "interest": [r"INTEREST\s*EARNED", r"DIVIDEND"],
            "penalty": [r"OVERDRAFT", r"LATE\s*FEE", r"PENALTY"],
        }
        for tx in self.transactions:
            desc = tx.get("description", "").upper()
            for flag, patterns in flags.items():
                if any(re.search(p, desc) for p in patterns):
                    tx["tax_flag"] = flag
                    break

    # ------------------------------------------------------------------
    # Output formats
    # ------------------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({"account_info": self.account_info, "transactions": self.transactions}, indent=2, default=str)

    def to_csv(self, path: Optional[str] = None) -> str:
        import io
        if not self.transactions:
            return ""
        sio = io.StringIO()
        fieldnames = ["date", "description", "amount", "type", "tax_flag"]
        writer = csv.DictWriter(sio, fieldnames=fieldnames)
        writer.writeheader()
        for tx in self.transactions:
            writer.writerow({k: tx.get(k, "") for k in fieldnames})
        result = sio.getvalue()
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write(result)
        return result

    def to_qif(self) -> str:
        lines = ["!Type:Bank"]
        for tx in self.transactions:
            date_raw = tx.get("date", "")
            try:
                date = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%m/%d/%Y") if date_raw else ""
            except ValueError:
                date = date_raw
            amount = tx.get("amount", 0) or 0
            desc = tx.get("description", "")
            lines.append(f"D{date}")
            lines.append(f"T{amount:.2f}")
            lines.append(f"P{desc}")
            lines.append("^")
        return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse a bank statement PDF")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--format", choices=["json", "csv", "qif"], default="json", help="Output format")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    args = parser.parse_args()

    p = GenericPDFParser(args.pdf_path)
    result = p.parse()

    if args.format == "json":
        output = json.dumps(result, indent=2, default=str)
    elif args.format == "csv":
        output = p.to_csv()
    elif args.format == "qif":
        output = p.to_qif()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Output written to {args.output}")
    else:
        print(output)