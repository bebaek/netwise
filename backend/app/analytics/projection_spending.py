from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.analytics.projection_contracts import (
    ProjectionAccount,
    ProjectionMortgage,
    ProjectionProperty,
    ProjectionSpendingItem,
)


def project_spending_items_for_period(
    spending_items: Sequence[ProjectionSpendingItem],
    retirement_date: date | None,
    baseline_year: int,
    period_start: date,
    period_end: date,
    months_per_period: int,
    default_growth_rate: Decimal,
) -> list[dict]:
    """Project each spending item independently and preserve its category breakdown."""
    breakdown = []
    for item in spending_items:
        growth_rate = item.growth_rate if item.growth_rate is not None else default_growth_rate
        retirement_amount = (
            item.retirement_annual_amount
            if item.retirement_annual_amount is not None
            else item.annual_amount
        )
        amount = project_spending_for_period(
            (baseline_year, item.annual_amount),
            (baseline_year, retirement_amount) if retirement_date is not None else None,
            retirement_date,
            period_start,
            period_end,
            months_per_period,
            growth_rate,
        )
        breakdown.append(
            {
                "name": item.name,
                "category": item.category,
                "amount": amount,
            }
        )
    return breakdown


def project_owner_property_spending_for_period(
    property_profiles: Sequence[ProjectionProperty],
    accounts_by_id: dict[UUID, ProjectionAccount],
    balances: dict[UUID, Decimal],
    start_year: int,
    period_start: date,
    period_end: date,
    months_per_period: int,
    spending_inflation_rate: Decimal,
) -> list[dict]:
    """Return inflation-adjusted owner property tax and insurance spending."""
    years_elapsed = max(period_start.year - start_year, 0)
    inflation_factor = (Decimal("1") + spending_inflation_rate) ** years_elapsed
    breakdown: list[dict] = []
    for profile in property_profiles:
        account = accounts_by_id.get(profile.account_id)
        if account is None or balances.get(profile.account_id, Decimal("0.00")) <= Decimal("0.00"):
            continue
        active_months = min(
            active_months_in_period(profile.purchase_date, period_start, period_end),
            months_per_period,
        )
        if active_months == 0:
            continue
        period_fraction = Decimal(active_months) / Decimal("12")
        if profile.tax_and_insurance_annual is not None:
            costs = [("property tax and insurance", profile.tax_and_insurance_annual)]
        else:
            costs = [
                ("property tax", profile.property_tax_annual or Decimal("0.00")),
                ("homeowners insurance", profile.insurance_annual or Decimal("0.00")),
            ]
        for label, annual_amount in costs:
            amount = (annual_amount * inflation_factor * period_fraction).quantize(Decimal("0.01"))
            if amount == Decimal("0.00"):
                continue
            breakdown.append(
                {
                    "name": f"{account.name} {label}",
                    "category": "housing",
                    "amount": amount,
                }
            )
    return breakdown


def project_owner_mortgage_spending_for_period(
    mortgage_profiles: Sequence[ProjectionMortgage],
    period_start: date,
    period_end: date,
    sold_mortgage_account_ids: set[UUID],
) -> Decimal:
    """Return fixed owner-occupied mortgage payments due during the period."""
    spending = Decimal("0.00")
    for profile in mortgage_profiles:
        if profile.liability_account_id in sold_mortgage_account_ids:
            continue
        active_months = scheduled_mortgage_payment_months(profile, period_start, period_end)
        if active_months == 0:
            continue
        monthly_payment = profile.monthly_payment or amortized_monthly_payment(profile)
        spending += monthly_payment * Decimal(active_months)
    return spending.quantize(Decimal("0.01"))


def scheduled_mortgage_payment_months(
    profile: ProjectionMortgage,
    period_start: date,
    period_end: date,
) -> int:
    """Count scheduled payment months overlapping an inclusive projection period."""
    period_start_month = period_start.year * 12 + period_start.month - 1
    period_end_month = period_end.year * 12 + period_end.month - 1
    origination_month = profile.start_date.year * 12 + profile.start_date.month - 1
    first_payment_month = origination_month + 1
    final_payment_month = origination_month + profile.term_months
    active_start = max(period_start_month, first_payment_month)
    active_end = min(period_end_month, final_payment_month)
    return max(active_end - active_start + 1, 0)


def project_spending_for_period(
    spending_baseline: tuple[int, Decimal] | None,
    retirement_spending_baseline: tuple[int, Decimal] | None,
    retirement_date: date | None,
    period_start: date,
    period_end: date,
    months_per_period: int,
    spending_inflation_rate: Decimal,
) -> Decimal:
    """Return inflation-adjusted spending, blending a retirement transition period."""
    working_annual_spending = project_spending_for_year(
        spending_baseline, period_start.year, spending_inflation_rate
    )
    retirement_annual_spending = project_spending_for_year(
        retirement_spending_baseline, period_start.year, spending_inflation_rate
    )
    period_fraction = Decimal(months_per_period) / Decimal("12")

    if retirement_date is None or retirement_spending_baseline is None:
        return (working_annual_spending * period_fraction).quantize(Decimal("0.01"))
    if retirement_date <= period_start:
        return (retirement_annual_spending * period_fraction).quantize(Decimal("0.01"))
    if retirement_date > period_end:
        return (working_annual_spending * period_fraction).quantize(Decimal("0.01"))

    period_days = Decimal((period_end - period_start).days + 1)
    retirement_days = Decimal((period_end - retirement_date).days + 1)
    working_days = period_days - retirement_days
    blended_annual_spending = (
        (working_annual_spending * working_days) + (retirement_annual_spending * retirement_days)
    ) / period_days
    return (blended_annual_spending * period_fraction).quantize(Decimal("0.01"))


def project_spending_for_year(
    spending_baseline: tuple[int, Decimal] | None,
    year: int,
    spending_inflation_rate: Decimal,
) -> Decimal:
    if spending_baseline is None:
        return Decimal("0.00")
    baseline_year, baseline_amount = spending_baseline
    years_elapsed = max(year - baseline_year, 0)
    return (baseline_amount * ((Decimal("1") + spending_inflation_rate) ** years_elapsed)).quantize(
        Decimal("0.01")
    )


def active_months_in_period(
    active_start_date: date | None,
    period_start: date,
    period_end: date,
) -> int:
    """Count active months in a period, including a partial starting month."""
    if active_start_date is None or active_start_date <= period_start:
        first_active_month = period_start
    elif active_start_date > period_end:
        return 0
    else:
        first_active_month = active_start_date
    return (
        (period_end.year - first_active_month.year) * 12
        + period_end.month
        - first_active_month.month
        + 1
    )


def amortized_monthly_payment(profile: ProjectionMortgage) -> Decimal:
    monthly_rate = profile.interest_rate / Decimal("12")
    if monthly_rate == Decimal("0.00"):
        return (profile.original_principal / Decimal(profile.term_months)).quantize(Decimal("0.01"))
    factor = (Decimal("1") + monthly_rate) ** profile.term_months
    return (profile.original_principal * monthly_rate * factor / (factor - Decimal("1"))).quantize(
        Decimal("0.01")
    )
