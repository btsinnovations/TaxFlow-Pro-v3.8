"""Detection tests for Tier 1 institution profiles in v3.9."""
import pytest

from backend.parsers import detect_institution, detect_institution_with_columns, INSTITUTION_ALIASES


TIER1_CASES = [
    ("Navy Federal", "NAVY FEDERAL CREDIT UNION STATEMENT"),
    ("U.S. Bank", "U.S. BANK CHECKING STATEMENT"),
    ("Citibank", "CITIBANK CREDIT CARD STATEMENT"),
    ("PNC Bank", "PNC BANK ONLINE STATEMENT"),
    ("Ally Bank", "ALLY BANK SAVINGS STATEMENT"),
    ("SoFi", "SoFi MONEY STATEMENT"),
    ("Truist", "TRUIST BANK CHECKING STATEMENT"),
    ("Discover Bank", "DISCOVER BANK STATEMENT"),
    ("Marcus by Goldman Sachs", "MARCUS BY GOLDMAN SACHS SAVINGS"),
    ("Marcus by Goldman Sachs", "MARCUS SAVINGS STATEMENT"),
    ("BECU", "BECU MEMBERS STATEMENT"),
    ("BECU", "Boeing Employees Credit Union checking"),
]


@pytest.mark.parametrize("expected,text", TIER1_CASES)
def test_detect_tier1_institution(expected, text):
    assert detect_institution(text) == expected


def test_detect_institution_unknown():
    assert detect_institution("Some Random PDF") == "unknown"


def test_detect_becu_from_synthetic_fixture():
    text = open("fixtures/becu_statement.txt").read()
    assert detect_institution(text) == "BECU"


def test_becu_layout_and_columns_from_synthetic_fixture():
    text = open("fixtures/becu_statement.txt").read()
    result = detect_institution_with_columns(text)
    assert result["institution"] == "BECU"
    assert result["layout"] == "multi_column"
    assert "transaction date" in result["expected_columns"]
    assert "withdrawal" in result["expected_columns"]
    assert result["confidence"] >= 0.5


def test_becu_alias_registered():
    assert "BECU" in INSTITUTION_ALIASES
    assert "Boeing Employees Credit Union" in INSTITUTION_ALIASES["BECU"]


def test_detect_with_columns_confidence_and_layout():
    result = detect_institution_with_columns("Navy Federal Credit Union transactions")
    assert result["institution"] == "Navy Federal"
    assert result["confidence"] >= 0.5
    assert result["layout"] == "multi_column"
    assert "transaction" in result["expected_columns"]


def test_detect_with_columns_single_column():
    result = detect_institution_with_columns("Cash App to Someone $10")
    assert result["institution"] == "Cash App"
    assert result["layout"] == "single_column"


def test_detect_with_columns_includes_notes():
    result = detect_institution_with_columns("Citibank checking statement")
    assert result["institution"] == "Citibank"
    assert "source" in result["notes"]
    assert "quirk" in result["notes"]


def test_detect_with_columns_unknown():
    result = detect_institution_with_columns("Random unrelated PDF")
    assert result["institution"] == "unknown"
    assert result["confidence"] == 0.0


def test_tier1_aliases_registered():
    for canonical, _ in TIER1_CASES:
        assert canonical in INSTITUTION_ALIASES, f"{canonical} missing aliases"
