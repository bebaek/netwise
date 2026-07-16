from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.net_worth import calculate_net_worth_history
from app.db.models import AccountEvent, AnnualTaxRecord, ProjectionBehavior


class ExpenseEstimateError(ValueError):
    pass


def estimate_annual_living_expense(db: Session, household_id: UUID, tax_year: int) -> dict:
    tax_record = db.scalars(
        select(AnnualTaxRecord).where(
            AnnualTaxRecord.household_id == household_id,
            AnnualTaxRecord.tax_year == tax_year,
        )
    ).first()
    if tax_record is None:
        raise ExpenseEstimateError("Annual tax record is required for expense estimation")
    if tax_record.gross_income is None:
        raise ExpenseEstimateError("Gross income is required for expense estimation")

    history = calculate_net_worth_history(db, household_id)
    year_points = [point for point in history["points"] if point["as_of_date"].year == tax_year]
    if len(year_points) < 2:
        raise ExpenseEstimateError("At least two net worth history points are required in the tax year")

    start_point = year_points[0]
    end_point = year_points[-1]
    net_worth_change = end_point["net_worth"] - start_point["net_worth"]
    adjustment_total = _historical_adjustment_total(
        db,
        household_id=household_id,
        start_date=start_point["as_of_date"],
        end_date=end_point["as_of_date"],
    )

    estimated_living_expense = (
        tax_record.gross_income
        - tax_record.total_taxes_paid
        - net_worth_change
        - adjustment_total
    )

    return {
        "household_id": household_id,
        "tax_year": tax_year,
        "period_start": start_point["as_of_date"],
        "period_end": end_point["as_of_date"],
        "gross_income": tax_record.gross_income,
        "taxes_paid": tax_record.total_taxes_paid,
        "net_worth_start": start_point["net_worth"],
        "net_worth_end": end_point["net_worth"],
        "net_worth_change": net_worth_change,
        "adjustment_total": adjustment_total,
        "estimated_living_expense": estimated_living_expense,
    }


def _historical_adjustment_total(
    db: Session,
    household_id: UUID,
    start_date: date,
    end_date: date,
) -> Decimal:
    events = db.scalars(
        select(AccountEvent).where(
            AccountEvent.household_id == household_id,
            AccountEvent.event_date >= start_date,
            AccountEvent.event_date <= end_date,
            AccountEvent.projection_behavior != ProjectionBehavior.projection_only,
        )
    ).all()
    return sum((event.amount for event in events), Decimal("0.00"))
