"""Depreciation service tests for TaxFlow Pro v3.9."""
from decimal import Decimal
from datetime import date

import pytest

from backend.services.depreciation import compute_schedule, verify_schedule_sums_to_cost_basis, MACRS_GDS_TABLES


def test_macrs_gds_five_year_schedule_sums_to_basis():
    cost = Decimal("10000.00")
    schedule = compute_schedule(cost, date(2024, 1, 15), 5)
    assert verify_schedule_sums_to_cost_basis(schedule, cost)
    assert len(schedule) == 6
    assert schedule[0].year == 2024


def test_macrs_gds_seven_year_schedule_sums_to_basis():
    cost = Decimal("50000.00")
    schedule = compute_schedule(cost, date(2024, 6, 1), 7)
    assert verify_schedule_sums_to_cost_basis(schedule, cost)
    assert len(schedule) == 8


def test_section_179_and_bonus_reduce_basis():
    cost = Decimal("10000.00")
    schedule = compute_schedule(cost, date(2024, 1, 15), 5, section_179=Decimal("2000.00"), bonus_depreciation=Decimal("80.00"))
    assert verify_schedule_sums_to_cost_basis(schedule, cost)
    # first year should have section 179 + bonus
    first = schedule[0]
    assert first.section_179 == Decimal("2000.00")
    assert first.bonus == Decimal("6400.00")  # 80% of remaining 8000


def test_salvage_value_reserved():
    cost = Decimal("10000.00")
    schedule = compute_schedule(cost, date(2024, 1, 15), 5, salvage_value=Decimal("1000.00"))
    assert verify_schedule_sums_to_cost_basis(schedule, cost - Decimal("1000.00"))
    # total depreciation deductions cannot exceed depreciable basis (9000)
    total = sum(e.regular_depreciation + e.section_179 + e.bonus for e in schedule)
    assert total <= cost - Decimal("1000.00") + Decimal("0.05")


def test_ads_straight_line_sums():
    cost = Decimal("12000.00")
    schedule = compute_schedule(cost, date(2024, 1, 15), 5, method="MACRS-ADS")
    assert verify_schedule_sums_to_cost_basis(schedule, cost)
    annuals = [e.regular_depreciation for e in schedule]
    assert all(a == annuals[0] for a in annuals)


def test_unsupported_period_raises():
    with pytest.raises(ValueError):
        compute_schedule(Decimal("1000.00"), date(2024, 1, 15), 4)


def test_unsupported_method_raises():
    with pytest.raises(ValueError):
        compute_schedule(Decimal("1000.00"), date(2024, 1, 15), 5, method="double-declining")
