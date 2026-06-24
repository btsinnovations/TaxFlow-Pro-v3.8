from decimal import Decimal
from phase3_pipeline.models import Transaction
from phase3_pipeline.split import should_split, parse_cashback

def test_should_split_cashback():
    t = Transaction(date="2026-01-01", description="ATM CASH BACK $40", amount=Decimal("-60.00"))
    assert should_split(t) is True

def test_parse_cashback():
    t = Transaction(date="2026-01-01", description="CASH BACK $25.50", amount=Decimal("-50.00"))
    assert parse_cashback(t.description) == Decimal("25.50")

def test_no_split():
    t = Transaction(date="2026-01-01", description="Coffee", amount=Decimal("-5.00"))
    assert should_split(t) is False
