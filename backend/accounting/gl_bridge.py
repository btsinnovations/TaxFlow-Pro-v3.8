"""GL Bridge — Automatic double-entry posting from transactions to GeneralLedgerEntry.

R1 Remediation: Every transaction import path generates balanced GL entries.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


# Fallback COA account numbers for uncategorized transactions
UNCATEGORIZED_INCOME_NUMBER = 4015
UNCATEGORIZED_EXPENSE_NUMBER = 5015
OPERATING_CHECKING_NUMBER = 1020


class GLBridge:
    """Post balanced double-entry GL pairs for transactions."""

    def __init__(self, db: Session, tenant_id: int, user_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

    def _get_or_create_coa(self, number: int, name: str, acct_type: str) -> models.CoaAccount:
        """Find or create a COA account by number."""
        existing = self.db.query(models.CoaAccount).filter(
            models.CoaAccount.tenant_id == self.tenant_id,
            models.CoaAccount.number == number,
        ).first()
        if existing:
            return existing
        account = models.CoaAccount(
            tenant_id=self.tenant_id,
            number=number,
            name=name,
            type=acct_type,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def ensure_offset_accounts_exist(self) -> None:
        """Create fallback COA accounts if missing."""
        self._get_or_create_coa(UNCATEGORIZED_INCOME_NUMBER, "Uncategorized Income", "income")
        self._get_or_create_coa(UNCATEGORIZED_EXPENSE_NUMBER, "Uncategorized Expense", "expense")
        self._get_or_create_coa(OPERATING_CHECKING_NUMBER, "Operating Checking", "asset")

    def _get_cash_coa(self, txn: models.Transaction) -> Optional[models.CoaAccount]:
        """Map a transaction's bank account to a COA asset account.

        A transaction's `coa_account_id` is the *offset* category (income/expense),
        never the cash account. Cash is resolved from the statement's bank account
        or the first asset account in the 1000-1999 range.
        """
        # Try to find a cash/asset COA account for this tenant
        cash = self.db.query(models.CoaAccount).filter(
            models.CoaAccount.tenant_id == self.tenant_id,
            models.CoaAccount.type == "asset",
            models.CoaAccount.number >= 1000,
            models.CoaAccount.number < 2000,
        ).first()
        if cash:
            return cash
        return self._get_or_create_coa(OPERATING_CHECKING_NUMBER, "Operating Checking", "asset")

    def _get_offset_coa(self, txn: models.Transaction) -> models.CoaAccount:
        """Determine the offset account for a transaction."""
        # 1. Explicit COA account on transaction
        if txn.coa_account_id:
            coa = self.db.query(models.CoaAccount).filter(
                models.CoaAccount.id == txn.coa_account_id,
            ).first()
            if coa:
                return coa

        # 2. CategorizationRule match by description
        rules = self.db.query(models.CategorizationRule).filter(
            models.CategorizationRule.tenant_id == self.tenant_id,
            models.CategorizationRule.enabled == True,
            models.CategorizationRule.coa_account_id.isnot(None),
        ).order_by(models.CategorizationRule.priority.desc()).all()

        desc_lower = (txn.description or "").lower()
        for rule in rules:
            if rule.pattern and rule.pattern.lower() in desc_lower:
                coa = self.db.query(models.CoaAccount).filter(
                    models.CoaAccount.id == rule.coa_account_id,
                ).first()
                if coa:
                    return coa

        # 4. Default fallback
        tx_type = (txn.tx_type or "").lower()
        if tx_type in ("credit", "deposit", "income"):
            return self._get_or_create_coa(UNCATEGORIZED_INCOME_NUMBER, "Uncategorized Income", "income")
        return self._get_or_create_coa(UNCATEGORIZED_EXPENSE_NUMBER, "Uncategorized Expense", "expense")

    def is_already_posted(self, txn: models.Transaction) -> bool:
        """Check if GL entries already exist for this transaction."""
        existing = self.db.query(models.GeneralLedgerEntry).filter(
            models.GeneralLedgerEntry.transaction_id == txn.id,
        ).first()
        return existing is not None

    def post_for_transaction(self, txn: models.Transaction) -> list[models.GeneralLedgerEntry]:
        """Post a balanced debit/credit pair for a single transaction."""
        if self.is_already_posted(txn):
            return []

        self.ensure_offset_accounts_exist()

        amount = Decimal(str(txn.amount or 0))
        if amount == 0:
            return []

        cash_coa = self._get_cash_coa(txn)
        offset_coa = self._get_offset_coa(txn)
        tx_type = (txn.tx_type or "").lower()

        entries: list[models.GeneralLedgerEntry] = []

        if tx_type in ("credit", "deposit", "income"):
            # Deposit: debit cash (asset), credit income/offset
            debit_coa = cash_coa
            credit_coa = offset_coa
        elif tx_type in ("debit", "withdrawal", "expense"):
            # Withdrawal/expense: credit cash (asset), debit expense/offset
            debit_coa = offset_coa
            credit_coa = cash_coa
        else:
            # Unknown type — treat as expense (debit offset, credit cash)
            debit_coa = offset_coa
            credit_coa = cash_coa

        entry_date = txn.date or date.today()
        description = txn.description or ""

        debit_entry = models.GeneralLedgerEntry(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            transaction_id=txn.id,
            date=entry_date,
            description=description,
            debit_coa_account_id=debit_coa.id if debit_coa else None,
            credit_coa_account_id=None,
            amount=amount,
            memo=f"Auto-posted from txn:{txn.id}",
            entry_type="regular",
            source_id=f"txn:{txn.id}",
            import_source=txn.import_source,
            txn_uid=txn.txn_uid,
        )
        credit_entry = models.GeneralLedgerEntry(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            transaction_id=txn.id,
            date=entry_date,
            description=description,
            debit_coa_account_id=None,
            credit_coa_account_id=credit_coa.id if credit_coa else None,
            amount=amount,
            memo=f"Auto-posted from txn:{txn.id}",
            entry_type="regular",
            source_id=f"txn:{txn.id}",
            import_source=txn.import_source,
            txn_uid=txn.txn_uid,
        )
        self.db.add_all([debit_entry, credit_entry])
        entries.extend([debit_entry, credit_entry])
        return entries

    def post_batch(self, txns: list[models.Transaction]) -> list[models.GeneralLedgerEntry]:
        """Post GL entries for a batch of transactions. Skips already-posted."""
        all_entries = []
        for txn in txns:
            entries = self.post_for_transaction(txn)
            all_entries.extend(entries)
        if all_entries:
            self.db.commit()
        return all_entries