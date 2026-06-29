from typing import List
from decimal import Decimal
from .models import Transaction
from .logger import Logger

logger = Logger("ledger_guard")

def validate_raw_transactions(transactions: List[Transaction]) -> bool:
    """
    Validate raw transactions before processing.
    Returns True if valid, False otherwise.
    """
    if not transactions:
        logger.error("No transactions to validate")
        return False

    seen = set()
    for t in transactions:
        if not t.txn_uid:
            logger.error("Missing txn_uid")
            return False
        if t.txn_uid in seen:
            logger.error(f"Duplicate txn_uid: {t.txn_uid}")
            return False
        seen.add(t.txn_uid)
        if t.amount == Decimal(0):
            logger.warning(f"Zero amount transaction: {t.txn_uid}")

    logger.info(f"Validation passed: {len(transactions)} transactions")
    return True
