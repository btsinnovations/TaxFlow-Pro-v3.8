"""
Phase 3.5.3 – Reconciliation Engine with PASS/FAIL/PARTIAL status.
Assumes Transaction.amount is negative for debits/expenses, positive for credits/income.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple, List
from .models import Transaction
from .logger import Logger

logger = Logger("reconciliation")


class ReconciliationReport:
    def __init__(self, file_name: str = ""):
        self.file_name = file_name
        self.opening_balance: Optional[Decimal] = None
        self.closing_balance: Optional[Decimal] = None
        self.transaction_count = 0
        self.total_credits = Decimal("0.00")
        self.total_debits = Decimal("0.00")
        self.net_change = Decimal("0.00")
        self.calculated_ending: Optional[Decimal] = None
        self.variance = Decimal("0.00")
        self.status = "PARTIAL"   # "PASS", "FAIL", "PARTIAL"
        self.message = ""

    def to_dict(self) -> dict:
        has_context = self.opening_balance is not None
        return {
            "file_name": self.file_name,
            "status": self.status,
            "opening_balance": f"{self.opening_balance:.2f}" if has_context else "N/A",
            "closing_balance": f"{self.closing_balance:.2f}" if self.closing_balance is not None else "N/A",
            "transaction_count": str(self.transaction_count),
            "total_credits": f"{self.total_credits:.2f}",
            "total_debits": f"{self.total_debits:.2f}",
            "net_change": f"{self.net_change:.2f}",
            "calculated_ending": f"{self.calculated_ending:.2f}" if self.calculated_ending is not None else "N/A",
            "variance": f"{self.variance:.2f}",
            "message": self.message,
        }


class StatementReconciler:
    DEFAULT_TOLERANCE = Decimal("0.02")

    def __init__(self, tolerance: Optional[Decimal] = None):
        self.tolerance = tolerance or self.DEFAULT_TOLERANCE

    def reconcile_transactions(
        self,
        transactions: List[Transaction],
        opening: Optional[Decimal] = None,
        closing: Optional[Decimal] = None,
    ) -> ReconciliationReport:
        report = ReconciliationReport()
        total = Decimal("0.00")
        credits = Decimal("0.00")
        debits = Decimal("0.00")
        # Safely handle 'is_tombstone' attribute
        live_txns = [t for t in transactions if not getattr(t, "is_tombstone", False)]

        # Assumption: amount > 0 → credit (income/deposit), amount < 0 → debit (expense/withdrawal)
        for t in live_txns:
            total += t.amount
            if t.amount > 0:
                credits += t.amount
            else:
                debits += t.amount

        report.transaction_count = len(live_txns)
        report.total_credits = credits
        report.total_debits = abs(debits)
        report.net_change = total
        report.opening_balance = opening
        report.closing_balance = closing

        if opening is not None:
            report.calculated_ending = opening + total

        if opening is not None and closing is not None:
            if report.calculated_ending is not None:
                report.variance = report.calculated_ending - closing
            else:
                report.variance = Decimal("0.00")
            if abs(report.variance) <= self.tolerance:
                report.status = "PASS"
                report.message = "Reconciliation successful"
            else:
                report.status = "FAIL"
                report.message = f"Variance: {report.variance:.2f}"
        else:
            report.status = "PARTIAL"
            report.message = "Partial reconciliation (missing statement balances)"

        logger.info(f"Reconciliation: {report.message} ({report.status})")
        return report

    @staticmethod
    def extract_balances_from_text(text: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        if not text:
            return None, None

        def _parse_decimal(num_str: str) -> Optional[Decimal]:
            try:
                return Decimal(num_str.replace(",", ""))
            except (InvalidOperation, ValueError, TypeError):
                return None

        # ----- EdFed SHARE DRAFT (bounded) -----
        share_draft_begin = re.search(
            r'SHARE\s+DRAFT\s+70\s+SUMMARY.*?Beginning\s+Balance\s+([\d,]+\.\d{2})',
            text,
            re.DOTALL | re.IGNORECASE
        )
        share_draft_end = re.search(
            r'SHARE\s+DRAFT\s+70\s+SUMMARY.*?Ending\s+Balance\s+([\d,]+\.\d{2})',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if share_draft_begin and share_draft_end:
            opening = _parse_decimal(share_draft_begin.group(1))
            closing = _parse_decimal(share_draft_end.group(1))
            if opening is not None and closing is not None:
                return opening, closing

        # ----- Standard patterns (bounded to avoid excessive backtracking) -----
        open_patterns = [
            r"(?:Opening|Beginning|Previous|Start)\s+Balance:?\s*\$?([\d,]+\.\d{2})",
            r"Balance\s+Forward:?\s*\$?([\d,]+\.\d{2})",
            r"BeginningBalance[:\s]*\$?([\d,]+\.\d{2})",
            r"Balance\s+on\s+\S{1,30}\s+\d{1,2},?\s+\d{4}:\s*\$?([\d,]+\.\d{2})",
        ]
        close_patterns = [
            r"(?:Closing|Ending|New|Current)\s+Balance:?\s*\$?([\d,]+\.\d{2})",
            r"Statement\s+Balance:?\s*\$?([\d,]+\.\d{2})",
            r"EndingBalance[:\s]*\$?([\d,]+\.\d{2})",
        ]

        opening = None
        closing = None

        for p in open_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                opening = _parse_decimal(m.group(1))
                if opening is not None:
                    break

        for p in close_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                closing = _parse_decimal(m.group(1))
                if closing is not None:
                    break

        # ----- EdFed "Total Balance" fallback (improved with non‑digit boundaries) -----
        if opening is None or closing is None:
            pair = re.search(
                r'Total\s+Balance[^0-9]{0,500}?([\d,]+\.\d{2})[^0-9]{0,500}?([\d,]+\.\d{2})',
                text,
                re.DOTALL | re.IGNORECASE
            )
            if pair:
                new_open = _parse_decimal(pair.group(1))
                new_close = _parse_decimal(pair.group(2))
                if opening is None and new_open is not None:
                    opening = new_open
                if closing is None and new_close is not None:
                    closing = new_close

        # ----- Cash App style (unchanged – works reliably) -----
        if opening is None or closing is None:
            cash_match = re.search(
                r'Balance\s+on.{0,100}?\$?([\d,]+\.\d{2}).{0,500}?Balance\s+on.{0,100}?\$?([\d,]+\.\d{2})',
                text,
                re.DOTALL | re.IGNORECASE
            )
            if cash_match:
                new_open = _parse_decimal(cash_match.group(1))
                new_close = _parse_decimal(cash_match.group(2))
                if opening is None and new_open is not None:
                    opening = new_open
                if closing is None and new_close is not None:
                    closing = new_close

        # ----- Chime style (bounded) -----
        if opening is None or closing is None:
            chime_open = re.search(
                r'Beginning\s+balance\s+on.{0,200}?\$?([\d,]+\.\d{2})',
                text,
                re.DOTALL | re.IGNORECASE
            )
            chime_close = re.search(
                r'Ending\s+balance\s+on.{0,200}?\$?([\d,]+\.\d{2})',
                text,
                re.DOTALL | re.IGNORECASE
            )
            if chime_open:
                new_open = _parse_decimal(chime_open.group(1))
                if opening is None and new_open is not None:
                    opening = new_open
            if chime_close:
                new_close = _parse_decimal(chime_close.group(1))
                if closing is None and new_close is not None:
                    closing = new_close

        return opening, closing


# Wrapper for backward compatibility
def reconcile_transactions(
    transactions: List[Transaction],
    opening: Optional[Decimal] = None,
    closing: Optional[Decimal] = None,
    tolerance: Decimal = Decimal("0.02"),
) -> ReconciliationReport:
    reconciler = StatementReconciler(tolerance)
    return reconciler.reconcile_transactions(transactions, opening, closing)
