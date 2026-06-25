"""Tests for v3.11 bank parser detection endpoint and parser interface contract."""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.parsers.institution import (
    INSTITUTION_ALIASES,
    _INSTITUTION_REGISTRY,
    detect_institution,
    detect_institution_with_columns,
)


FIXTURES_DIR = Path(__file__).with_name("fixtures") / "parsers"


EXPECTED_INSTITUTIONS = sorted({entry[0] for entry in _INSTITUTION_REGISTRY})


@pytest.fixture(scope="module")
def fixture_map() -> dict[str, Path]:
    """Map canonical institution names to synthetic fixture file paths."""
    slug_map = {
        "TD Bank": "td_bank.txt",
        "Bank of America": "bank_of_america.txt",
        "Chase": "chase.txt",
        "Chime": "chime.txt",
        "EdFed": "edfed.txt",
        "Queensborough National Bank": "queensborough.txt",
        "Wells Fargo": "wells_fargo.txt",
        "Cash App": "cash_app.txt",
        "Navy Federal": "navy_federal.txt",
        "U.S. Bank": "us_bank.txt",
        "Citibank": "citibank.txt",
        "PNC Bank": "pnc_bank.txt",
        "Ally Bank": "ally_bank.txt",
        "SoFi": "sofi.txt",
        "Truist": "truist.txt",
        "BECU": "becu.txt",
        "Discover Bank": "discover_bank.txt",
        "Marcus by Goldman Sachs": "marcus.txt",
    }
    return {name: FIXTURES_DIR / filename for name, filename in slug_map.items()}


def _load_fixture(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("institution", EXPECTED_INSTITUTIONS)
def test_detect_institution_from_fixture(institution: str, fixture_map: dict[str, Path]):
    """Every registered institution is detected from its synthetic fixture text."""
    path = fixture_map.get(institution)
    assert path is not None, f"Missing fixture mapping for {institution}"
    assert path.exists(), f"Missing fixture file: {path}"
    text = _load_fixture(path)
    detected = detect_institution(text)
    assert detected == institution, f"Expected {institution}, got {detected}"


@pytest.mark.parametrize("institution", EXPECTED_INSTITUTIONS)
def test_detect_with_columns_returns_expected_columns(institution: str, fixture_map: dict[str, Path]):
    """Detection returns expected columns and positive confidence for each fixture."""
    path = fixture_map[institution]
    text = _load_fixture(path)
    result = detect_institution_with_columns(text)
    assert result["institution"] == institution
    assert result["confidence"] > 0
    assert len(result["expected_columns"]) > 0
    assert "layout" in result
    assert "notes" in result


def test_detect_unknown_text_returns_zero_confidence():
    result = detect_institution_with_columns("Some random grocery receipt from 2026")
    assert result["institution"] == "unknown"
    assert result["confidence"] == 0.0
    assert result["expected_columns"] == []


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("Navy FCU", "Navy Federal"),
        ("US Bank", "U.S. Bank"),
        ("Citi", "Citibank"),
        ("PNC", "PNC Bank"),
        ("Boeing Employees Credit Union", "BECU"),
        ("Marcus", "Marcus by Goldman Sachs"),
    ],
)
def test_aliases_detect(alias: str, expected: str):
    text = f"{alias}\nStatement Period: 01/01/2026 - 01/31/2026\nDate Description Debit Credit Balance\n"
    detected = detect_institution(text)
    assert detected == expected, f"Expected {expected} for alias {alias}, got {detected}"


@pytest.mark.parametrize("canonical,aliases", list(INSTITUTION_ALIASES.items()))
def test_aliases_list_non_empty(canonical: str, aliases: list[str]):
    assert canonical in {entry[0] for entry in _INSTITUTION_REGISTRY}
    assert len(aliases) > 0
    assert all(isinstance(a, str) and a.strip() for a in aliases)


# ---------------------------------------------------------------------------
# Parser interface contract
# ---------------------------------------------------------------------------

SPECIFIC_PARSER_MODULES = [
    "backend.parsers.tdbank",
    "backend.parsers.chime",
    "backend.parsers.edfed",
    "backend.parsers.queensborough",
]


def _module_has_parser_class(module_name: str) -> tuple[bool, str]:
    """Check whether a parser module exposes a class with can_handle() and parse()."""
    mod = importlib.import_module(module_name)
    for _name, obj in inspect.getmembers(mod, inspect.isclass):
        # Ignore imported classes from parser_base.
        if obj.__module__ != module_name:
            continue
        if hasattr(obj, "can_handle") and hasattr(obj, "parse"):
            return True, _name
    return False, ""


@pytest.mark.parametrize("module_name", SPECIFIC_PARSER_MODULES)
def test_parser_interface_contract(module_name: str):
    """Every institution-specific parser module exposes a can_handle() + parse() class."""
    has_parser, class_name = _module_has_parser_class(module_name)
    assert has_parser, f"{module_name} does not expose a parser class with can_handle()/parse()"
    mod = importlib.import_module(module_name)
    cls = getattr(mod, class_name)
    assert callable(getattr(cls, "can_handle", None))
    assert callable(getattr(cls, "parse", None))


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------


def test_api_detect_import(auth_client: TestClient):
    text = _load_fixture(FIXTURES_DIR / "chase.txt")
    resp = auth_client.post("/api/imports/detect", json={"text": text})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["institution"] == "Chase"
    assert body["confidence"] > 0
    assert "expected_columns" in body


def test_api_detect_import_with_rows(auth_client: TestClient):
    rows = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["01/02/2026", "PAYROLL", "", "2,500.00", "2,500.00"],
        ["01/05/2026", "Chase Manhattan", "75.00", "", "2,425.00"],
    ]
    resp = auth_client.post("/api/imports/detect", json={"text": "Statement", "rows": rows})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["institution"] == "Chase"


def test_api_detect_import_unknown(auth_client: TestClient):
    resp = auth_client.post("/api/imports/detect", json={"text": "Grocery receipt from 2026"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["institution"] == "unknown"
