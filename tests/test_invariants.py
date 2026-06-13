import pytest
from decimal import Decimal
from phase3_pipeline.models import Transaction
from phase3_pipeline.graph import TransactionGraph
from phase3_pipeline.invariants import validate

def test_duplicate_id_fails():
    g = TransactionGraph()
    t1 = Transaction(date="2026-01-01", description="A", amount=Decimal("10"), txn_uid="same")
    t2 = Transaction(date="2026-01-01", description="B", amount=Decimal("20"), txn_uid="same")
    g.add(t1)
    g.add(t2)
    with pytest.raises(ValueError, match="Duplicate txn_uid"):
        validate(g)
