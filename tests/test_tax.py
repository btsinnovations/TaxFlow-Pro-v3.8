from decimal import Decimal
from phase3_pipeline.models import Transaction
from phase3_pipeline.tax import classify_transaction

def test_classify_fuel():
    t = Transaction(date="2026-01-01", description="SHELL OIL", amount=Decimal("-45.00"))
    cat, line, ded = classify_transaction(t)
    assert cat == "fuel_expense"
    assert ded is True

def test_tombstone_skipped():
    t = Transaction(date="2026-01-01", description="SHELL OIL", amount=Decimal("-45.00"), is_tombstone=True)
    cat, line, ded = classify_transaction(t)
    assert cat == "tombstone"