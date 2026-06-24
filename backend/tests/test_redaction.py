"""Tests for PII/PCI redaction helpers (TASK-038.3)."""
from __future__ import annotations

import csv
import io

from backend.utils.redaction import (
    mask_account_number,
    mask_transaction_description,
    redact_description,
    redact_text,
)
from backend.local.guards import redact_sensitive_values


def test_mask_account_number_last_four():
    assert mask_account_number("1234567890123456") == "************3456"
    assert mask_account_number("1234-5678-9012-3456") == "************3456"
    assert mask_account_number("1234567890") == "******7890"


def test_mask_account_number_short_value():
    assert mask_account_number("123") == "***"
    assert mask_account_number("1234") == "****"


def test_mask_account_number_non_digit_passthrough():
    assert mask_account_number("already-masked") == "already-masked"
    assert mask_account_number(None) is None
    assert mask_account_number("") == ""


def test_redact_description_replaces_text():
    assert redact_description("SALARY DEPOSIT") == "[REDACTED]"
    assert redact_description(None) is None


def test_redact_text_replaces_text():
    assert redact_text("some secret note") == "[REDACTED]"
    assert redact_text(None) is None


def test_mask_transaction_description_scrubs_long_digits():
    desc = "PAYMENT TO ACME INC ACCOUNT 123456789"
    assert mask_transaction_description(desc) == "PAYMENT TO ACME INC ACCOUNT *****6789"


def test_mask_transaction_description_keeps_short_digits():
    desc = "COFFEE SHOP #42"
    assert mask_transaction_description(desc) == "COFFEE SHOP #42"


def test_redact_sensitive_values_in_dict():
    payload = {
        "account_number": "1234567890123456",
        "card_number": "4111111111111111",
        "routing_number": "021000021",
        "description": "WIRE TRANSFER TO BOB",
        "amount": 100.0,
    }
    out = redact_sensitive_values(payload)
    assert out["account_number"] == "************3456"
    assert out["card_number"] == "************1111"
    assert out["routing_number"] == "*****0021"
    assert out["description"] == "[REDACTED]"
    assert out["amount"] == 100.0


def test_csv_export_service_masks_account_columns():
    from backend.services.export import _mask_text_fields

    header = ["id", "date", "description", "account_number", "amount"]
    rows = [
        header,
        ["1", "2025-01-01", "PAYMENT ACCT 123456789", "1234567890123456", "100.00"],
    ]
    masked = _mask_text_fields(rows, header)
    assert masked[1][3] == "************3456"
    assert masked[1][2] == "PAYMENT ACCT *****6789"
