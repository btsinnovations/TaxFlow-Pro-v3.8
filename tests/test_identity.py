import pytest
from decimal import Decimal
from phase3_pipeline.identity import IdentityService

def test_uid_stability():
    uid1 = IdentityService.generate("01/15/2025", "AMAZON MKTPLACE", Decimal("-45.67"), "Chase")
    uid2 = IdentityService.generate("01/15/2025", "Amazon Marketplace", Decimal("-45.67"), "Chase")
    assert uid1 == uid2

def test_uid_duplicate_detection():
    txns = [
        ("01/15/2025", "WAL-MART #123", Decimal("-20.00"), "EdFed"),
        ("01/15/2025", "Walmart", Decimal("-20.00"), "EdFed"),
    ]
    uids = [IdentityService.generate(d, desc, amt, inst) for d, desc, amt, inst in txns]
    assert uids[0] == uids[1]