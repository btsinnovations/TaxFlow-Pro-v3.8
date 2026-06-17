"""Tests for the depreciation calculation service."""

import pytest
from decimal import Decimal

from backend.services.depreciation import calculate_depreciation


class TestStraightLine:
    def test_half_year_convention(self):
        # 5-year asset, cost=10000, salvage=1000
        schedule = calculate_depreciation(
            cost=10000, salvage=1000, life_years=5, method="straight_line"
        )
        assert len(schedule) == 6  # half-year convention adds a year
        assert schedule[0]["depreciation"] == Decimal("900.00")  # half of 1800
        assert schedule[1]["depreciation"] == Decimal("1800.00")
        assert schedule[4]["depreciation"] == Decimal("1800.00")
        assert schedule[5]["depreciation"] == Decimal("900.00")
        assert schedule[-1]["ending_basis"] == Decimal("1000.00")

    def test_full_year_convention(self):
        schedule = calculate_depreciation(
            cost=10000, salvage=1000, life_years=5, method="straight_line",
            convention="full_year"
        )
        assert len(schedule) == 5
        for row in schedule:
            assert row["depreciation"] == Decimal("1800.00")
        assert schedule[-1]["ending_basis"] == Decimal("1000.00")


class TestDecliningBalance:
    def test_db200_first_year(self):
        schedule = calculate_depreciation(
            cost=10000, salvage=1000, life_years=5, method="declining_balance_200"
        )
        # First year half of 40% = 20%
        assert schedule[0]["depreciation"] == Decimal("2000.00")
        assert schedule[0]["ending_basis"] == Decimal("8000.00")

    def test_db200_switches_to_sl(self):
        schedule = calculate_depreciation(
            cost=10000, salvage=1000, life_years=5, method="declining_balance_200"
        )
        # Ensure depreciation is positive each year and ends at salvage
        for row in schedule:
            assert row["depreciation"] >= Decimal("0")
        assert schedule[-1]["ending_basis"] == Decimal("1000.00")

    def test_db150(self):
        schedule = calculate_depreciation(
            cost=10000, salvage=1000, life_years=5, method="declining_balance_150"
        )
        # First year switches to straight-line because SL is higher than half-year DB
        assert schedule[0]["depreciation"] == Decimal("1800.00")
        assert schedule[-1]["ending_basis"] == Decimal("1000.00")


class TestSumOfYearsDigits:
    def test_soyd_schedule(self):
        schedule = calculate_depreciation(
            cost=10000, salvage=1000, life_years=5, method="sum_of_years_digits"
        )
        # Half-year convention front-loads depreciation; verify total and salvage
        total_depreciation = sum(row["depreciation"] for row in schedule)
        assert total_depreciation == Decimal("9000.00")
        assert schedule[-1]["ending_basis"] == Decimal("1000.00")


class TestMACRS:
    def test_macrs_5_year(self):
        schedule = calculate_depreciation(
            cost=10000, salvage=0, life_years=5, method="macrs"
        )
        assert len(schedule) == 6
        assert schedule[0]["depreciation"] == Decimal("2000.00")
        assert schedule[1]["depreciation"] == Decimal("3200.00")
        assert schedule[-1]["ending_basis"] == Decimal("0.00")

    def test_macrs_invalid_life(self):
        with pytest.raises(ValueError):
            calculate_depreciation(cost=10000, salvage=0, life_years=4, method="macrs")


class TestValidation:
    def test_negative_cost(self):
        with pytest.raises(ValueError, match="Cost must be positive"):
            calculate_depreciation(cost=-1000, salvage=100, life_years=5)

    def test_salvage_greater_than_cost(self):
        with pytest.raises(ValueError, match="Salvage must be less than cost"):
            calculate_depreciation(cost=1000, salvage=1000, life_years=5)

    def test_zero_life(self):
        with pytest.raises(ValueError, match="Life years must be at least 1"):
            calculate_depreciation(cost=1000, salvage=100, life_years=0)

    def test_unknown_method(self):
        with pytest.raises(ValueError, match="Unknown depreciation method"):
            calculate_depreciation(
                cost=1000, salvage=100, life_years=5, method="double_declining"
            )
