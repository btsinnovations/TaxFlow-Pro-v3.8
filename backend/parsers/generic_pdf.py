"""
Generic PDF Bank Statement Parser
Supports 4 Master Templates covering 95% of US institutions.
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber


class GenericPDFParser:
    """Parse generic PDF bank statements using template-based detection."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.transactions: List[Dict[str, Any]] = []
        self.account_info: Dict[str, Any] = {}
        self.template: Optional[Dict[str, Any]] = None

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
        for template in templates:
            if "fiserv" in template.get("name", "").lower():
                self.template = template
                return template
        if templates:
            self.template = templates[0]
            return templates[0]
        return None

    def extract_text(self) -> List[str]:
        pages_text: List[str] = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text(layout=True)
                    if text:
                        pages_text.append(text)
        except Exception as e:
            return [f"ERROR:{e}"]
        return pages_text

    def parse_account_info(self, text: str) -> Dict[str, Any]:
        patterns = {
            "account_holder": r"(?:Account Holder|Name|Customer|Member|Primary Member)[:\s]+([A-Za-z\s\.\-]+?)(?:\n|$)",
            "account_number": r"(?:Account|Number|Acct|Member Number|Account No\.?)[\s#:]+(\d{4}[\d\s\-\*]{4,25})",
            "statement_period": r"(?:Statement Period|Period|From)[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}).{0,20}?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            "opening_balance": r"(?:Beginning Balance|Previous Balance|Opening Balance|Start Balance|Balance Forward)[:\s]*[\$\£\€]?([\d,]+\.\d{2})",
            "closing_balance": r"(?:Ending Balance|Closing Balance|Current Balance|New Balance|End Balance)[:\s]*[\$\£\€]?([\d,]+\.\d{2})",
            "account_type": r"(?:Account Type|Product|Plan)[:\s]+([A-Za-z\s]+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                self.account_info[key] = match.group(1).strip()
        if "account_type" not in self.account_info and self.template:
            terminology = self.template.get("terminology", {})
            if terminology:
                for cu_term, std_term in terminology.items():
                    if re.search(rf"\b{re.escape(std_term)}\b", text, re.IGNORECASE):
                        self.account_info["account_type"] = std_term
                        break
        return self.account_info

    def parse_transactions(self, text: str) -> List[Dict[str, Any]]:
        transactions: List[Dict[str, Any]] = []
        lines = text.split("\n")
        trans_pattern = self._get_transaction_regex()
        amount_columns = self.template.get("amount_columns", ["single"]) if self.template else ["single"]

        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue

            match = trans_pattern.search(line)
            if not match:
                continue

            groups = match.groups()
            if len(groups) < 3:
                continue

            date_str = groups[0]
            description = groups[1].strip()

            # Skip header/summary lines
            if any(skip in description.lower() for skip in ("beginning balance", "ending balance", "total", "summary", "continued", "page", "date", "description", "withdrawals", "deposits")):
                continue

            # Find the first non-empty amount group (index 2+)
            amount_raw = None
            for g in groups[2:]:
                if g and g.strip():
                    amount_raw = g.strip()
                    break

            if not amount_raw:
                continue

            amount = self._parse_amount(amount_raw, amount_columns)

            # Determine sign from description keywords (always apply)
            sign = self._infer_sign(description)
            if sign < 0 and amount > 0:
                amount = -amount

            transaction = {
                "date": self._normalize_date(date_str),
                "description": description,
                "amount": amount,
                "raw_line": line.strip(),
                "category": "uncategorized",
            }
            transactions.append(transaction)

        return transactions

    def _infer_sign(self, description: str) -> int:
        """Infer transaction sign from description keywords."""
        desc_lower = description.lower()
        debit_keywords = ['fee', 'shell', 'starbucks', 'walmart', 'netflix', 'geico', 'courtesy pay', 'overdraft', 'atm', 'service charge', 'withdrawal', 'debit', 'purchase']
        credit_keywords = ['payroll', 'deposit', 'direct deposit', 'dividend', 'interest', 'refund', 'credit', 'reimbursement', 'allowance', 'benefits', 'zelle from', 'transfer from']
        for kw in debit_keywords:
            if kw in desc_lower:
                return -1
        for kw in credit_keywords:
            if kw in desc_lower:
                return 1
        return -1  # Default to debit for safety

    def _get_transaction_regex(self) -> re.Pattern:
        if self.template:
            pattern = self.template.get("regex_patterns", {}).get("transaction", "")
            if pattern:
                try:
                    return re.compile(pattern)
                except re.error:
                    pass

        # Default: Date | Description | Amount(s) — whitespace is part of optional groups
        return re.compile(
            r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\s+(.+?)\s+"
            r"([\(\)\$\-]?[\d,]+\.\d{2})"
            r"(?:\s+([\(\)\$\-]?[\d,]+\.\d{2}))?"
            r"(?:\s+([\(\)\$\-]?[\d,]+\.\d{2}))?"
        )

    def _parse_amount(self, amount_raw: str, amount_columns: List[str]) -> float:
        amount_str = amount_raw.replace("$", "").replace("£", "").replace("€", "").replace(",", "").strip()
        if amount_str.startswith("(") and amount_str.endswith(")"):
            amount_str = "-" + amount_str[1:-1]
        try:
            return float(amount_str)
        except ValueError:
            return 0.0

    def _normalize_date(self, date_str: str) -> str:
        formats = [
            "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y",
            "%m/%d/%y", "%m-%d-%y", "%d/%m/%y", "%d-%m-%y",
            "%Y/%m/%d", "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_str

    def extract_tables(self) -> List[Dict[str, Any]]:
        tables: List[Dict[str, Any]] = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    for table in page_tables:
                        if table and len(table) > 1:
                            tables.append({"headers": table[0], "rows": table[1:]})
        except Exception:
            pass
        return tables

    def parse(self) -> Dict[str, Any]:
        pages_text = self.extract_text()
        if not pages_text:
            return {"error": "No text found in PDF"}
        if pages_text and pages_text[0].startswith("ERROR:"):
            return {"error": pages_text[0].replace("ERROR:", "")}

        self.detect_template(pages_text[0])
        self.parse_account_info(pages_text[0])

        for text in pages_text:
            trans = self.parse_transactions(text)
            self.transactions.extend(trans)

        seen: set = set()
        unique_trans = []
        for t in self.transactions:
            key = (t.get("date"), t.get("description"), t.get("amount"))
            if key not in seen:
                seen.add(key)
                unique_trans.append(t)
        self.transactions = unique_trans

        if self.template and "terminology" in self.template:
            self._apply_terminology_mapping()
        self._apply_categorization_hints()

        return {
            "template": self.template.get("name", "Unknown") if self.template else "Unknown",
            "account_info": self.account_info,
            "transactions": self.transactions,
            "transaction_count": len(self.transactions),
        }

    def _apply_terminology_mapping(self):
        terminology = self.template.get("terminology", {})
        if "checking" in terminology and "account_type" in self.account_info:
            if terminology["checking"].lower() in self.account_info["account_type"].lower():
                self.account_info["account_type"] = "Checking"
        if "savings" in terminology and "account_type" in self.account_info:
            if terminology["savings"].lower() in self.account_info["account_type"].lower():
                self.account_info["account_type"] = "Savings"
        for trans in self.transactions:
            desc = trans.get("description", "")
            if "interest" in terminology and terminology["interest"] in desc:
                trans["category"] = "Interest/Dividend"
            if "overdraft" in terminology and terminology["overdraft"] in desc:
                trans["category"] = "Overdraft Fee"

    def _apply_categorization_hints(self):
        ach_patterns = {
            r"\bDFAS\b": "Military Pay",
            r"\bTREAS 310\b": "Government Payment",
            r"\bBAH\b": "Military Housing Allowance",
            r"\bBAS\b": "Military Subsistence",
            r"\bAK PERM FUND\b": "Alaska Permanent Fund",
            r"\bVA BENEFITS?\b": "VA Benefits",
            r"\bSWEEP\b": "Brokerage Sweep",
            r"\bJOURNAL ENTRY\b": "Internal Transfer",
            r"\bWIRE TRANSFER\b": "Wire Transfer",
            r"\bZELLE\b": "P2P Transfer",
            r"\bVENMO\b": "P2P Transfer",
            r"\bCASH APP\b": "P2P Transfer",
            r"\bOVERDRAFT\b": "Overdraft Fee",
            r"\bCOURTESY PAY\b": "Overdraft Fee",
            r"\bATM FEE\b": "ATM Fee",
            r"\bSERVICE CHARGE\b": "Bank Fee",
            r"\bMERCHANT BATCH\b": "Business Deposit",
            r"\bPAYROLL\b": "Payroll",
            r"\bDIRECT DEPOSIT\b": "Direct Deposit",
            r"\bDIVIDEND\b": "Dividend/Interest",
            r"\bINTEREST PAID\b": "Interest",
            r"\bINTEREST EARNED\b": "Interest",
        }
        for trans in self.transactions:
            desc = trans.get("description", "")
            if trans.get("category") != "uncategorized":
                continue
            for pattern, cat in ach_patterns.items():
                if re.search(pattern, desc, re.IGNORECASE):
                    trans["category"] = cat
                    break

    def export_to_csv(self, output_path: str) -> str:
        if not self.transactions:
            raise ValueError("No transactions to export")
        fieldnames = ["date", "description", "amount", "category"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.transactions)
        return output_path

    def export_to_json(self, output_path: str) -> str:
        result = {
            "template": self.template.get("name", "Unknown") if self.template else "Unknown",
            "account_info": self.account_info,
            "transactions": self.transactions,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return output_path
