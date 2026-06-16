"""
Depreciation router: calculate depreciation schedules, return IRS MACRS tables,
and list available depreciation methods.
"""
from datetime import datetime
from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .auth import get_current_user

router = APIRouter(prefix="/depreciation", tags=["depreciation"])

# IRS MACRS half-year convention percentages (3, 5, 7, 10, 15, 20-year property)
MACRS_TABLES = {
    "3": {
        "name": "3-Year Property",
        "years": [33.33, 44.45, 14.81, 7.41],
    },
    "5": {
        "name": "5-Year Property",
        "years": [20.00, 32.00, 19.20, 11.52, 11.52, 5.76],
    },
    "7": {
        "name": "7-Year Property",
        "years": [14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46],
    },
    "10": {
        "name": "10-Year Property",
        "years": [10.00, 18.00, 14.40, 11.52, 9.22, 7.37, 6.55, 6.55, 6.56, 6.55, 3.28],
    },
    "15": {
        "name": "15-Year Property",
        "years": [5.00, 9.50, 8.55, 7.70, 6.93, 6.23, 5.90, 5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 2.95],
    },
    "20": {
        "name": "20-Year Property",
        "years": [3.750, 7.219, 6.677, 6.177, 5.713, 5.285, 4.888, 4.522, 4.462, 4.461,
                  4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 2.231],
    },
    "27.5": {
        "name": "27.5-Year Residential Rental",
        "years": [3.485] * 28,
    },
    "39": {
        "name": "39-Year Nonresidential Real Property",
        "years": [2.564] * 39,
    },
}

# Section 179 limits
SECTION_179_LIMIT_2024 = 1250000
SECTION_179_PHASEOUT_2024 = 3130000


class DepreciationMethod(BaseModel):
    code: str
    name: str
    description: str


class DepreciationRequest(BaseModel):
    asset_name: str
    asset_class: str
    cost_basis: float
    placed_in_service_date: str
    recovery_period: float
    method: Literal["macrs_hy", "macrs_mq", "straight_line", "section_179", "bonus_60"]
    section_179_expense: float = 0.0
    bonus_depreciation_pct: float = 0.0
    salvage_value: float = 0.0
    business_use_pct: float = 100.0


class DepreciationYearEntry(BaseModel):
    year: int
    beginning_basis: float
    deduction: float
    ending_basis: float
    method: str


class DepreciationResponse(BaseModel):
    asset_name: str
    asset_class: str
    cost_basis: float
    recovery_period: float
    method: str
    business_use_pct: float
    section_179_expense: float
    bonus_depreciation: float
    depreciable_basis: float
    total_deduction: float
    schedule: List[DepreciationYearEntry]


@router.get("/methods", response_model=List[DepreciationMethod])
def list_methods(
    current_user: models.User = Depends(get_current_user),
):
    return [
        DepreciationMethod(
            code="macrs_hy", name="MACRS (Half-Year)",
            description="Modified Accelerated Cost Recovery System with half-year convention"
        ),
        DepreciationMethod(
            code="macrs_mq", name="MACRS (Mid-Quarter)",
            description="MACRS with mid-quarter convention for assets placed in service in Q4"
        ),
        DepreciationMethod(
            code="straight_line", name="Straight-Line",
            description="Equal annual deductions over recovery period"
        ),
        DepreciationMethod(
            code="section_179", name="Section 179 Expense",
            description="Immediate expensing up to annual limit (2024: $1,250,000)"
        ),
        DepreciationMethod(
            code="bonus_60", name="Bonus Depreciation (60%)",
            description="60% first-year bonus depreciation for qualifying property placed in service 2025"
        ),
    ]


@router.get("/macrs-tables")
def get_macrs_tables(
    current_user: models.User = Depends(get_current_user),
):
    return {
        property_type: {
            "name": data["name"],
            "yearly_percentages": data["years"],
            "total_years": len(data["years"]),
        }
        for property_type, data in MACRS_TABLES.items()
    }


def _get_macrs_rates(recovery_period: float) -> List[float]:
    key = str(int(recovery_period)) if recovery_period == int(recovery_period) else str(recovery_period)
    if key in MACRS_TABLES:
        return MACRS_TABLES[key]["years"]
    # Fallback to straight-line for unknown periods
    n = int(recovery_period)
    rate = 100.0 / n
    return [round(rate, 2)] * n


@router.post("/calculate", response_model=DepreciationResponse)
def calculate_depreciation(
    req: DepreciationRequest,
    current_user: models.User = Depends(get_current_user),
):
    if req.cost_basis <= 0:
        raise HTTPException(status_code=400, detail="Cost basis must be positive")
    if req.recovery_period <= 0:
        raise HTTPException(status_code=400, detail="Recovery period must be positive")
    if not (0 < req.business_use_pct <= 100):
        raise HTTPException(status_code=400, detail="Business use percentage must be between 0 and 100")

    try:
        pis_year = datetime.strptime(req.placed_in_service_date, "%Y-%m-%d").year
    except ValueError:
        raise HTTPException(status_code=400, detail="placed_in_service_date must be YYYY-MM-DD")

    section_179 = min(req.section_179_expense, SECTION_179_LIMIT_2024, req.cost_basis)
    if section_179 < 0:
        section_179 = 0

    bonus = req.cost_basis * (req.bonus_depreciation_pct / 100.0)
    depreciable_basis = req.cost_basis - section_179 - bonus - req.salvage_value
    if depreciable_basis < 0:
        depreciable_basis = 0

    bus_pct = req.business_use_pct / 100.0

    schedule = []

    if req.method == "section_179":
        schedule.append(DepreciationYearEntry(
            year=pis_year,
            beginning_basis=req.cost_basis,
            deduction=round(section_179 * bus_pct, 2),
            ending_basis=round(req.cost_basis - section_179, 2),
            method="section_179",
        ))
        total_deduction = section_179 * bus_pct

    elif req.method == "straight_line":
        annual = depreciable_basis / req.recovery_period
        remaining = depreciable_basis
        basis = req.cost_basis - section_179 - bonus
        for i in range(int(req.recovery_period)):
            deduction = round(min(annual, remaining) * bus_pct, 2)
            schedule.append(DepreciationYearEntry(
                year=pis_year + i,
                beginning_basis=round(basis, 2),
                deduction=deduction,
                ending_basis=round(max(basis - annual, 0), 2),
                method="straight_line",
            ))
            basis = max(basis - annual, 0)
            remaining = max(remaining - annual, 0)
        total_deduction = sum(y.deduction for y in schedule)

    elif req.method == "bonus_60":
        bonus60 = req.cost_basis * 0.60
        remainder = req.cost_basis - bonus60 - section_179
        rates = _get_macrs_rates(req.recovery_period)
        basis = remainder
        for i, rate in enumerate(rates):
            if i == 0:
                deduction = round((bonus60 * bus_pct) + (basis * (rate / 100.0) * bus_pct), 2)
            else:
                deduction = round(basis * (rate / 100.0) * bus_pct, 2)
            schedule.append(DepreciationYearEntry(
                year=pis_year + i,
                beginning_basis=round(basis, 2),
                deduction=deduction,
                ending_basis=round(basis * (1 - rate / 100.0), 2),
                method="bonus_60",
            ))
            basis = basis * (1 - rate / 100.0)
        total_deduction = sum(y.deduction for y in schedule) + (section_179 * bus_pct)

    else:
        # MACRS half-year (default)
        rates = _get_macrs_rates(req.recovery_period)
        basis = depreciable_basis
        for i, rate in enumerate(rates):
            deduction = round(basis * (rate / 100.0) * bus_pct, 2)
            schedule.append(DepreciationYearEntry(
                year=pis_year + i,
                beginning_basis=round(basis, 2),
                deduction=deduction,
                ending_basis=round(basis * (1 - rate / 100.0), 2),
                method=req.method,
            ))
            basis = basis * (1 - rate / 100.0)
        total_deduction = sum(y.deduction for y in schedule) + (section_179 * bus_pct) + (bonus * bus_pct)

    return DepreciationResponse(
        asset_name=req.asset_name,
        asset_class=req.asset_class,
        cost_basis=req.cost_basis,
        recovery_period=req.recovery_period,
        method=req.method,
        business_use_pct=req.business_use_pct,
        section_179_expense=round(section_179, 2),
        bonus_depreciation=round(bonus, 2),
        depreciable_basis=round(depreciable_basis, 2),
        total_deduction=round(total_deduction, 2),
        schedule=schedule,
    )
