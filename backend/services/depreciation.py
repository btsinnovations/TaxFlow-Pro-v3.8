"""
Depreciation calculation service.

Supports five depreciation methods:
  - straight_line
  - declining_balance_200 (double declining, 200% of SL rate)
  - declining_balance_150 (150% declining balance)
  - sum_of_years_digits
  - macrs (IRS Modified Accelerated Cost Recovery System)

All methods return a list of period dictionaries with:
    {year, beginning_basis, depreciation, ending_basis}

MACRS uses IRS Publication 946 tables for 3/5/7/10/15/20-year property
with half-year convention baked in.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Literal


MethodType = Literal[
    "straight_line",
    "declining_balance_200",
    "declining_balance_150",
    "sum_of_years_digits",
    "macrs",
]

ConventionType = Literal["half_year", "mid_quarter", "full_year"]

# ---------------------------------------------------------------------------
# IRS MACRS percentage tables (from IRS Pub 946, Appendix A)
# Half-year convention baked in.  Each list sums to 100.0.
# ---------------------------------------------------------------------------
_MACRS_TABLES = {
    3: [33.33, 44.45, 14.81, 7.41],
    5: [20.00, 32.00, 19.20, 11.52, 11.52, 5.76],
    7: [14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46],
    10: [10.00, 18.00, 14.40, 11.52, 9.22, 7.37, 6.55, 6.55, 6.56, 6.55, 3.28],
    15: [
        5.00, 9.50, 8.55, 7.70, 6.93, 6.23, 5.90, 5.90, 5.91, 5.90,
        5.91, 5.90, 5.91, 5.90, 5.91, 2.95,
    ],
    20: [
        3.750, 7.219, 6.677, 6.177, 5.713, 5.285, 4.888, 4.522, 4.462, 4.461,
        4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461,
        2.231,
    ],
}


def _d(val) -> Decimal:
    """Convert a numeric value to a Decimal with 2 decimal places."""
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _validate_inputs(cost: Decimal, salvage: Decimal, life_years: int) -> None:
    """Validate common inputs across all depreciation methods."""
    if cost <= 0:
        raise ValueError("Cost must be positive")
    if salvage < 0:
        raise ValueError("Salvage cannot be negative")
    if salvage >= cost:
        raise ValueError("Salvage must be less than cost")
    if life_years < 1:
        raise ValueError("Life years must be at least 1")


def _build_schedule(
    beginning_basis: Decimal,
    yearly_depreciation: List[Decimal],
) -> List[dict]:
    """Build a standard schedule from a list of yearly depreciation amounts."""
    schedule = []
    basis = beginning_basis
    for year_idx, dep in enumerate(yearly_depreciation, start=1):
        dep = dep.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Ensure we do not depreciate below zero
        if dep > basis:
            dep = basis
        ending = (basis - dep).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if ending < Decimal("0"):
            ending = Decimal("0")
        schedule.append({
            "year": year_idx,
            "beginning_basis": basis,
            "depreciation": dep,
            "ending_basis": ending,
        })
        basis = ending
    return schedule


def _straight_line_schedule(
    cost: Decimal,
    salvage: Decimal,
    life_years: int,
    convention: ConventionType = "half_year",
) -> List[dict]:
    """Straight-line depreciation with convention support."""
    depreciable_base = cost - salvage
    annual_sl = depreciable_base / life_years

    if convention == "half_year":
        first_year = annual_sl / 2
        last_year = annual_sl / 2
        middle_years = [annual_sl] * (life_years - 1)
        yearly = [first_year] + middle_years + [last_year]
    elif convention == "full_year":
        yearly = [annual_sl] * life_years
    else:
        # mid_quarter falls back to SL without proration for simplicity
        yearly = [annual_sl] * life_years

    return _build_schedule(cost, yearly)


def _declining_balance_schedule(
    cost: Decimal,
    salvage: Decimal,
    life_years: int,
    rate_multiplier: Decimal,
    convention: ConventionType = "half_year",
) -> List[dict]:
    """
    Declining balance with optional switch to straight-line.
    rate_multiplier: 2.0 for 200% DB, 1.5 for 150% DB.
    """
    sl_rate = Decimal("1") / life_years
    db_rate = sl_rate * rate_multiplier

    schedule = []
    basis = cost
    remaining_years = life_years

    for year_idx in range(1, life_years + 1):
        # Half-year convention: first year gets half the DB rate
        if convention == "half_year" and year_idx == 1:
            rate_for_year = db_rate / 2
        elif convention == "half_year" and year_idx == life_years:
            # Last year also half to account for the first-year half
            rate_for_year = db_rate / 2
        else:
            rate_for_year = db_rate

        db_dep = (basis * rate_for_year).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Switch to straight-line if SL gives higher depreciation
        if remaining_years > 0:
            sl_dep = ((basis - salvage) / remaining_years).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            sl_dep = Decimal("0")

        dep = max(db_dep, sl_dep)

        # Ensure we don't go below salvage
        if basis - dep < salvage:
            dep = basis - salvage
            if dep < Decimal("0"):
                dep = Decimal("0")

        ending = (basis - dep).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        schedule.append({
            "year": year_idx,
            "beginning_basis": basis,
            "depreciation": dep,
            "ending_basis": ending,
        })
        basis = ending
        remaining_years -= 1

        if basis <= salvage:
            break

    return schedule


def _sum_of_years_digits_schedule(
    cost: Decimal,
    salvage: Decimal,
    life_years: int,
    convention: ConventionType = "half_year",
) -> List[dict]:
    """Sum-of-years-digits depreciation with half-year convention."""
    depreciable_base = cost - salvage
    total_digits = sum(range(1, life_years + 1))

    # Generate fractional depreciation for each year
    fractions = []
    for year in range(life_years, 0, -1):
        fractions.append(Decimal(year) / Decimal(total_digits))

    # Half-year convention: first year gets half, last year gets the other half
    if convention == "half_year":
        adjusted = []
        for i, frac in enumerate(fractions):
            if i == 0:
                adjusted.append(frac / 2)
            elif i == len(fractions) - 1:
                adjusted.append(frac + (fractions[0] / 2))
            else:
                adjusted.append(frac)
        fractions = adjusted

    yearly = [(depreciable_base * f).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
              for f in fractions]
    return _build_schedule(cost, yearly)


def _macrs_schedule(
    cost: Decimal,
    life_years: int,
) -> List[dict]:
    """
    IRS MACRS schedule using official half-year convention tables.
    MACRS ignores salvage value.
    """
    if life_years not in _MACRS_TABLES:
        raise ValueError(
            f"MACRS life_years must be one of {list(_MACRS_TABLES.keys())}, "
            f"got {life_years}"
        )

    percentages = _MACRS_TABLES[life_years]
    yearly = [
        (cost * Decimal(str(pct)) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        for pct in percentages
    ]
    return _build_schedule(cost, yearly)


def calculate_depreciation(
    cost,
    salvage,
    life_years: int,
    method: MethodType = "straight_line",
    convention: ConventionType = "half_year",
) -> List[dict]:
    """
    Calculate depreciation schedule.

    Parameters
    ----------
    cost : Decimal or numeric
        Original cost basis of the asset.
    salvage : Decimal or numeric
        Estimated salvage value at end of useful life.
    life_years : int
        Useful life of the asset in years.
    method : str
        One of: straight_line, declining_balance_200,
        declining_balance_150, sum_of_years_digits, macrs.
    convention : str
        One of: half_year, mid_quarter, full_year.
        Only half_year is fully implemented for DB and SOYD.

    Returns
    -------
    list[dict]
        Each dict has keys: year (int), beginning_basis (Decimal),
        depreciation (Decimal), ending_basis (Decimal).
    """
    cost = _d(cost)
    salvage = _d(salvage)

    if method == "macrs":
        # MACRS ignores salvage; validate just cost and life
        if cost <= 0:
            raise ValueError("Cost must be positive")
        if life_years < 1:
            raise ValueError("Life years must be at least 1")
        return _macrs_schedule(cost, life_years)

    _validate_inputs(cost, salvage, life_years)

    if method == "straight_line":
        return _straight_line_schedule(cost, salvage, life_years, convention)
    elif method == "declining_balance_200":
        return _declining_balance_schedule(
            cost, salvage, life_years, Decimal("2.0"), convention
        )
    elif method == "declining_balance_150":
        return _declining_balance_schedule(
            cost, salvage, life_years, Decimal("1.5"), convention
        )
    elif method == "sum_of_years_digits":
        return _sum_of_years_digits_schedule(cost, salvage, life_years, convention)
    else:
        raise ValueError(f"Unknown depreciation method: {method}")
