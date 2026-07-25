from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.analytics.projection_contracts import ProjectionIncomeSource

DEFAULT_INCOME_GROWTH_RATE = Decimal("0.020000")
INCOME_FREQUENCY_MULTIPLIERS = {
    "weekly": Decimal("52"),
    "biweekly": Decimal("26"),
    "semimonthly": Decimal("24"),
    "monthly": Decimal("12"),
    "quarterly": Decimal("4"),
    "annually": Decimal("1"),
}


def project_income_for_year(
    income_sources: Sequence[ProjectionIncomeSource],
    year: int,
) -> Decimal:
    return sum(
        (project_income_source_for_year(source, year) for source in income_sources),
        Decimal("0.00"),
    )


def project_income_source_for_period(
    source: ProjectionIncomeSource,
    period_start: date,
    period_end: date,
    months_per_period: int,
) -> Decimal:
    """Allocate an active income source across a monthly, quarterly, or annual period.

    Income is currently spread evenly across active months. The explicit period
    width remains part of the policy contract so a future payroll scheduler can
    replace this approximation without changing timeline orchestration.
    """
    if source.start_date > period_end or (
        source.end_date is not None and source.end_date < period_start
    ):
        return Decimal("0.00")
    annual_amount = project_income_source_for_year(source, period_start.year)
    active_start = max(source.start_date, period_start)
    active_end = min(source.end_date, period_end) if source.end_date is not None else period_end
    active_months = (
        (active_end.year - active_start.year) * 12 + active_end.month - active_start.month + 1
    )
    return (annual_amount * Decimal(active_months) / Decimal("12")).quantize(Decimal("0.01"))


def project_income_source_for_year(source: ProjectionIncomeSource, year: int) -> Decimal:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    if source.start_date > year_end or (
        source.end_date is not None and source.end_date < year_start
    ):
        return Decimal("0.00")

    annual_amount = annualize_income(source.amount, source.frequency)
    growth_rate = (
        source.growth_rate if source.growth_rate is not None else DEFAULT_INCOME_GROWTH_RATE
    )
    years_elapsed = max(year - source.start_date.year, 0)
    return (annual_amount * ((Decimal("1") + growth_rate) ** years_elapsed)).quantize(
        Decimal("0.01")
    )


def annualize_income(amount: Decimal, frequency: str) -> Decimal:
    return amount * INCOME_FREQUENCY_MULTIPLIERS.get(frequency, Decimal("1"))
