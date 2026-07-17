from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.analytics.expense_estimation import ExpenseEstimateError, estimate_annual_living_expense
from app.analytics.historical_trend import calculate_historical_trend
from app.analytics.net_worth import (
    calculate_net_worth,
    calculate_net_worth_breakdown_history,
    calculate_net_worth_history,
)
from app.analytics.projections import calculate_net_worth_projection
from app.db.models import Household
from app.db.session import get_db
from app.schemas.dashboard import (
    AnnualExpenseEstimateRead,
    HistoricalTrendRead,
    NetWorthBreakdownHistoryRead,
    NetWorthHistoryRead,
    NetWorthRead,
)
from app.schemas.projection import NetWorthProjectionRead

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{household_id}/net-worth", response_model=NetWorthRead)
def get_net_worth(household_id: UUID, db: Session = Depends(get_db)) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    return calculate_net_worth(db, household_id)


@router.get("/{household_id}/net-worth/history", response_model=NetWorthHistoryRead)
def get_net_worth_history(household_id: UUID, db: Session = Depends(get_db)) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    return calculate_net_worth_history(db, household_id)


@router.get("/{household_id}/breakdown-history", response_model=NetWorthBreakdownHistoryRead)
def get_net_worth_breakdown_history(household_id: UUID, db: Session = Depends(get_db)) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    return calculate_net_worth_breakdown_history(db, household_id)


@router.get("/{household_id}/historical-trend", response_model=HistoricalTrendRead)
def get_historical_trend(
    household_id: UUID,
    interpolate: bool = False,
    interval: str = "month",
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        return calculate_historical_trend(
            db,
            household_id,
            interpolate=interpolate,
            interval=interval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{household_id}/projection", response_model=NetWorthProjectionRead)
def get_net_worth_projection(
    household_id: UUID,
    start_year: int,
    end_year: int,
    annual_spending: Decimal | None = None,
    spending_inflation_rate: Decimal = Decimal("0.030000"),
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        return calculate_net_worth_projection(
            db,
            household_id,
            start_year=start_year,
            end_year=end_year,
            annual_spending=annual_spending,
            spending_inflation_rate=spending_inflation_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{household_id}/expense-estimates/{tax_year}",
    response_model=AnnualExpenseEstimateRead,
)
def get_annual_expense_estimate(
    household_id: UUID,
    tax_year: int,
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        return estimate_annual_living_expense(db, household_id=household_id, tax_year=tax_year)
    except ExpenseEstimateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
