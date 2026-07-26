from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.analytics.historical_trend import calculate_historical_trend
from app.analytics.net_worth import (
    calculate_net_worth,
    calculate_net_worth_breakdown_history,
    calculate_net_worth_history,
)
from app.analytics.projection_comparison import compare_projection_scenarios
from app.analytics.projections import calculate_net_worth_projection
from app.db.models import Household
from app.db.session import get_db
from app.schemas.dashboard import (
    HistoricalTrendRead,
    NetWorthBreakdownHistoryRead,
    NetWorthHistoryRead,
    NetWorthRead,
)
from app.schemas.projection import (
    NetWorthProjectionRead,
    ProjectionComparisonRead,
    ProjectionComparisonRequest,
)

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


@router.post(
    "/{household_id}/projection-comparison",
    response_model=ProjectionComparisonRead,
)
def compare_net_worth_projections(
    household_id: UUID,
    payload: ProjectionComparisonRequest,
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        return compare_projection_scenarios(
            db,
            household_id,
            scenario_ids=payload.scenario_ids,
            start_year=payload.start_year,
            end_year=payload.end_year,
            interval=payload.interval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{household_id}/projection", response_model=NetWorthProjectionRead)
def get_net_worth_projection(
    household_id: UUID,
    start_year: int,
    end_year: int,
    scenario_id: UUID | None = None,
    annual_spending: Decimal | None = None,
    spending_inflation_rate: Decimal | None = None,
    spending_account_id: UUID | None = None,
    tax_account_id: UUID | None = None,
    interval: str = "annual",
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        return calculate_net_worth_projection(
            db,
            household_id,
            scenario_id=scenario_id,
            start_year=start_year,
            end_year=end_year,
            annual_spending=annual_spending,
            spending_inflation_rate=spending_inflation_rate,
            spending_account_id=spending_account_id,
            tax_account_id=tax_account_id,
            interval=interval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
