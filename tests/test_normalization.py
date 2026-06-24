import pytest
from decimal import Decimal
from phase3_pipeline.normalization import normalize_date, normalize_amount

def test_normalize_date_iso():
    assert normalize_date("2026-06-09") == "2026-06-09"

def test_normalize_date_us():
    assert normalize_date("06/09/2026") == "2026-06-09"

def test_normalize_date_eu():
    assert normalize_date("09.06.2026") == "2026-06-09"

def test_normalize_amount_usd():
    assert normalize_amount("$1,234.56") == Decimal("1234.56")

def test_normalize_amount_negative_parens():
    assert normalize_amount("(45.00)") == Decimal("-45.00")