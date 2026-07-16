from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.analytics.expense_estimation import ExpenseEstimateError, estimate_annual_living_expense
from app.analytics.net_worth import calculate_net_worth, calculate_net_worth_history
from app.db.models import Household
from app.db.session import get_db
from app.schemas.dashboard import AnnualExpenseEstimateRead, NetWorthHistoryRead, NetWorthRead

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
