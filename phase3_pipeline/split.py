import re
from decimal import Decimal
from .identity import IdentityService
from .models import Transaction
from .config import SPLIT_PATTERNS, DEFAULT_CASHBACK
from .logger import Logger

logger = Logger("split")

def parse_cashback(text: str) -> Decimal:
    for pattern, _ in sorted(SPLIT_PATTERNS, key=lambda x: x[1]):
        m = re.search(pattern, text.lower())
        if m:
            return Decimal(m.group(1)).quantize(Decimal("0.01"))
    return Decimal(DEFAULT_CASHBACK).quantize(Decimal("0.01"))

def should_split(txn: Transaction) -> bool:
    text = txn.description.lower()
    for pattern, _ in SPLIT_PATTERNS:
        if re.search(pattern, text):
            logger.info(f"Splitting transaction: {txn.description[:80]}")
            return True
    return False

def apply_split(graph, txn: Transaction, idx: int):
    # Mark parent as tombstone
    txn.is_tombstone = True
    graph.add(txn)

    total = abs(txn.amount)
    cashback = min(parse_cashback(txn.description), total)
    purchase = total - cashback

    base = IdentityService.generate(txn.date, txn.description, txn.amount, txn.institution, idx)

    sign = -1 if txn.amount < 0 else 1

    purchase_txn = Transaction(
        date=txn.date,
        description=txn.description,
        raw_description=txn.raw_description,
        amount=Decimal(sign) * purchase,
        institution=txn.institution,
        category=txn.category,
        payee=txn.payee,
        txn_uid=base + "-p",
        parent_txn_uid=txn.txn_uid,
        split_flag=True,
        original_amount=txn.amount,
        split_group_id=txn.txn_uid,
        split_reason="cashback_split",
    )

    cash_txn = Transaction(
        date=txn.date,
        description="Cash Back",
        raw_description=f"Cash Back from {txn.description}",
        amount=Decimal(sign) * cashback,
        institution=txn.institution,
        category="Cash Withdrawal",
        payee="Cash",
        txn_uid=base + "-c",
        parent_txn_uid=txn.txn_uid,
        split_flag=True,
        original_amount=txn.amount,
        split_group_id=txn.txn_uid,
        split_reason="cashback_split",
    )

    graph.add(purchase_txn)
    graph.add(cash_txn)
