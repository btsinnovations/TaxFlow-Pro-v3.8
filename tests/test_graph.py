import pytest
from decimal import Decimal
from phase3_pipeline.models import Transaction
from phase3_pipeline.graph import TransactionGraph

def test_add_node():
    g = TransactionGraph()
    t = Transaction(date="2026-01-01", description="Test", amount=Decimal("10.00"), txn_uid="a")
    g.add(t)
    assert t.txn_uid in g.nodes

<<<<<<< HEAD
def test_duplicate_raises():
=======
def test_duplicate_stored_and_validated():
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    g = TransactionGraph()
    t1 = Transaction(date="2026-01-01", description="Test", amount=Decimal("10.00"), txn_uid="a")
    t2 = Transaction(date="2026-01-01", description="Test", amount=Decimal("10.00"), txn_uid="a")
    g.add(t1)
<<<<<<< HEAD
    with pytest.raises(ValueError, match="Duplicate txn_uid"):
        g.add(t2)
=======
    g.add(t2)  # Graph now records duplicates for later invariant validation
    assert len(g.all()) == 2
    from phase3_pipeline.invariants import validate
    with pytest.raises(ValueError, match="Duplicate txn_uid"):
        validate(g)
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd

def test_orphan_validation():
    g = TransactionGraph()
    parent = Transaction(date="2026-01-01", description="Parent", amount=Decimal("100"), txn_uid="p")
    child = Transaction(date="2026-01-01", description="Child", amount=Decimal("-50"), txn_uid="c", parent_txn_uid="p")
    g.add(child)  # add child first; parent not yet present
    with pytest.raises(ValueError, match="Orphan parent"):
        g.validate_orphans()