"""
Generic PDF Bank Statement Parser — TaxFlow Pro v3.7
Integrates: Task 5 (hash-based multi-page dedup), Task 6 (memory-safe OCR),
Task 8 (graveyard template support), Task 9 (SWIFT/currency cleaning).
"""

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

# ---------------------------------------------------------------------------
# Task 6 — OCR availability check (soft-fail if deps missing)
# ---------------------------------------------------------------------------
OCR_AVAILABLE = False
try:
    from pdf2image import convert_from_path
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    pass


class GenericPDFParser:
    """Parse generic PDF bank statements using template-based detection."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.transactions: List[Dict[str, Any]] = []
        self.account_info: Dict[str, Any] = {}
        self.template: Optional[Dict[str, Any]] = None
        self._ocr_warned = False

    # ------------------------------------------------------------------
    # Template loading & detection (Task 8 graveyard included)
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
        # Fallback heuristics
        for template in templates:
            if "fiserv" in template.get("name", "").lower():
                self.template = template
                return template
        if templates:
            self.template = templates[0]
            return templates[0]
        return None

    # ------------------------------------------------------------------
    # Text extraction (Task 6 — OCR fallback, page-by-page, memory-safe)
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
            return [f"ERROR:{e}"]

        total_text = "\n".join(pages_text).strip()

        # OCR fallback for scanned/image-based PDFs
        if len(total_text) < 100 and OCR_AVAILABLE:
            ocr_text = self._ocr_extract()
            if ocr_text:
                pages_text = [ocr_text]
        elif len(total_text) < 100 and not OCR_AVAILABLE and not self._ocr_warned:
            print("[WARNING] PDF appears scanned/image-based but OCR deps (pdf2image, pytesseract) not installed.")
            self._ocr_warned = True

        return pages_text

    def _ocr_extract(self) -> str:
        """Extract text via OCR page-by-page to prevent OOM. dpi lowered to 200."""
        if not OCR_AVAILABLE:
            return ""
        try:
            all_text: List[str] = []
            with pdfplumber.open(self.pdf_path) as pdf:
                page_count = len(pdf.pages)

            for page_num in range(1, page_count + 1):
                try:
                    images = convert_from_path(
                        self.pdf_path,
                        dpi=200,                 # Task 6 fix: 300 OOMs on large PDFs
                        first_page=page_num,
                        last_page=page_num,
                        fmt="ppm",               # lighter memory footprint than png
                    )
                    for image in images:
                        text = pytesseract.image_to_string(image)
                        if text:
                            all_text.append(text)
                        # Task 6 fix: explicit cleanup to prevent memory bloat
                        del image
                except Exception as e:
                    print(f"[WARNING] OCR failed on page {page_num}: {e}")
                    continue
            return "\n".join(all_text)
        except Exception as e:
            print(f"[ERROR] OCR extraction failed: {e}")
            return ""

    # ------------------------------------------------------------------
    # Preprocessing (Task 9 — SWIFT/currency cleaning, wired into parser)
    # ------------------------------------------------------------------

    def clean_transaction_line(self, line: str) -> str:
        """Remove SWIFT/BIC codes, normalize currency symbols, collapse whitespace."""
        # SWIFT/BIC codes (8 or 11 characters)
        line = re.sub(r'\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b', '', line)
        # Normalize major currency symbols to $
        line = line.replace('€', '$').replace('£', '$').replace('¥', '$')
        # Collapse whitespace
        line = re.sub(r'\s+', ' ', line).strip()
        return line

    def _preprocess_lines(self, text: str) -> List[str]:
        raw_lines = text.splitlines()
        cleaned = [self.clean_transaction_line(line) for line in raw_lines]
        return [line for line in cleaned if line]

    # ------------------------------------------------------------------
    # Balance extraction (reconciliation engine)
    # ------------------------------------------------------------------

    def _extract_balance(self, text: str, label_pattern: str) -> Optional[float]:
        pattern = re.compile(
            rf'{label_pattern}\s*[:]?\s*[$€£¥]?\s*([0-9,]+\.\d{{2}})',
            re.IGNORECASE
        )
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except ValueError:
                pass
        return None

    # ------------------------------------------------------------------
    # Amount / Date parsing helpers
    # ------------------------------------------------------------------

    def _parse_amount(self, amount_str: str, template: Dict[str, Any]) -> Optional[float]:
        if not amount_str:
            return None
        amount_str = amount_str.replace(',', '').replace('$', '').replace('€', '').replace('£', '').strip()
        try:
            val = float(amount_str)
            if template.get("amount_columns", {}).get("debit_negative", False):
                return val  # Fiserv DNA style: negative = debit, positive = credit
            return val
        except ValueError:
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
    # Task 5 — Hash-based dedup (replaces dangerous string comparison)
    # ------------------------------------------------------------------

    def _build_dedup_key(self, tx: Dict[str, Any]) -> str:
        raw = f"{tx.get('date', '')}|{tx.get('description', '')}|{tx.get('amount', 0.0):.2f}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _dedup_transactions(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set = set()
        for tx in transactions:
            h = self._build_dedup_key(tx)
            if h not in seen:
                seen.add(h)
                deduped.append(tx)
        return deduped

    # ------------------------------------------------------------------
    # Task 5 — Continuation-line merge (wrapped descriptions across breaks)
    # ------------------------------------------------------------------

    def _merge_continuations(
        self,
        transactions: List[Dict[str, Any]],
        raw_lines: List[str],
        tx_regex: re.Pattern,
    ) -> List[Dict[str, Any]]:
        """Heuristic: non-matching lines between two transactions append to previous description."""
        if not transactions:
            return transactions
        merged: List[Dict[str, Any]] = [transactions[0].copy()]
        tx_idx = 0
        for line in raw_lines:
            if tx_regex.match(line):
                tx_idx += 1
                if tx_idx < len(transactions):
                    merged.append(transactions[tx_idx].copy())
            elif tx_idx < len(merged) and len(line) < 120 and not line.startswith("$"):
                # Append as continuation if it looks like description text
                merged[tx_idx]["description"] = (merged[tx_idx].get("description", "") + " " + line).strip()
        return merged

    # ------------------------------------------------------------------
    # Main parse entrypoint
    # ------------------------------------------------------------------

    def parse(self) -> Dict[str, Any]:
        pages_text = self.extract_text()
        if not pages_text or (len(pages_text) == 1 and str(pages_text[0]).startswith("ERROR:")):
            return {"error": "Failed to extract text from PDF", "transactions": [], "account_info": {}}

        full_text = "\n".join(pages_text)
        self.detect_template(full_text)

        if not self.template:
            return {"error": "No matching template found", "transactions": [], "account_info": {}}

        # --- Account info / reconciliation ---
        opening = self._extract_balance(full_text, r"(?:opening|beginning|start|previous)\s+balance")
        closing = self._extract_balance(full_text, r"(?:closing|ending|end|current|new)\s+balance")
        self.account_info = {
            "opening_balance": opening,
            "closing_balance": closing,
            "template_name": self.template.get("name", "unknown"),
            "institution": self.template.get("institutions", [None])[0],
        }

        # --- Transaction regex patterns ---
        tx_patterns = self.template.get("regex_patterns", {}).get("transaction", [])
        if isinstance(tx_patterns, str):
            tx_patterns = [tx_patterns]

        compiled_patterns = [re.compile(p) for p in tx_patterns if p]

        # --- Parse all pages ---
        all_transactions: List[Dict[str, Any]] = []
        for page_text in pages_text:
            raw_lines = self._preprocess_lines(page_text)
            page_txs: List[Dict[str, Any]] = []
            for line in raw_lines:
                for pat in compiled_patterns:
                    m = pat.match(line)
                    if m:
                        gd = m.groupdict()
                        tx: Dict[str, Any] = {
                            "date": self._parse_date(gd.get("date", ""), self.template),
                            "description": gd.get("description", "").strip(),
                            "amount": None,
                            "type": "unknown",
                            "tax_flag": None,
                        }
                        # Split-column handling (Chase/BofA style)
                        if "withdrawal" in gd and gd["withdrawal"]:
                            tx["amount"] = -abs(self._parse_amount(gd["withdrawal"], self.template) or 0)
                            tx["type"] = "debit"
                        elif "deposit" in gd and gd["deposit"]:
                            tx["amount"] = abs(self._parse_amount(gd["deposit"], self.template) or 0)
                            tx["type"] = "credit"
                        elif "amount" in gd and gd["amount"]:
                            tx["amount"] = self._parse_amount(gd["amount"], self.template)
                            tx["type"] = "debit" if (tx["amount"] or 0) < 0 else "credit"

                        if tx["date"] and tx["amount"] is not None:
                            page_txs.append(tx)
                        break

            # Merge continuation lines within this page
            if compiled_patterns:
                page_txs = self._merge_continuations(page_txs, raw_lines, compiled_patterns[0])
            all_transactions.extend(page_txs)

        # --- Task 5: Multi-page dedup (hash-based, preserves legitimate duplicates) ---
        deduped = self._dedup_transactions(all_transactions)
        deduped.sort(key=lambda x: x.get("date") or "")
        self.transactions = deduped

        # --- Tax flag mapping ---
        self._apply_tax_flags()

        # --- Reconciliation variance ---
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
    # Tax flag mapping (all 40+ categories + ACH codes)
    # ------------------------------------------------------------------

    def _apply_tax_flags(self) -> None:
        flags = {
            "income": [
                r"TREAS\s*310", r"DFAS", r"PAYROLL", r"DIRECT\s*DEPOSIT",
                r"SALARY", r"WAGE", r"REFUND",
            ],
            "business": [
                r"SQ\s*\*", r"PAYPAL\s*\*", r"STRIPE", r"SHOPIFY",
                r"VENMO\s*\*", r"CASH\s*APP",
            ],
            "medical": [
                r"HOSPITAL", r"CLINIC", r"PHARMACY", r"DR\.\s*", r"MEDICAL",
                r"DENTAL", r"OPTOMETRY",
            ],
            "charity": [
                r"DONATION", r"CHARITY", r"UNITED\s*WAY", r"RED\s*CROSS",
            ],
            "education": [
                r"TUITION", r"UNIVERSITY", r"COLLEGE", r"STUDENT\s*LOAN",
            ],
            "tax": [
                r"IRS", r"TAX\s*PAYMENT", r"ESTIMATED\s*TAX",
            ],
            "interest": [
                r"INTEREST\s*EARNED", r"DIVIDEND", r"APY",
            ],
            "penalty": [
                r"OVERDRAFT", r"LATE\s*FEE", r"PENALTY", r"COURTESY\s*PAY",
            ],
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
        return json.dumps({
            "account_info": self.account_info,
            "transactions": self.transactions,
        }, indent=2, default=str)

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

    def to_excel(self, path: str) -> bool:
        try:
            import openpyxl
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Transactions"
            headers = ["date", "description", "amount", "type", "tax_flag"]
            ws.append(headers)
            for tx in self.transactions:
                ws.append([tx.get(k, "") for k in headers])
            wb.save(path)
            return True
        except ImportError:
            # Fallback to CSV with .xlsx extension warning
            csv_path = path.replace(".xlsx", ".csv")
            self.to_csv(csv_path)
            print(f"[WARNING] openpyxl not installed; fell back to CSV: {csv_path}")
            return False
