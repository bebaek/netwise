from datetime import date
from decimal import Decimal

from app.analytics.projection_contracts import ProjectionIncomeSource
from app.analytics.projection_income import (
    annualize_income,
    project_income_for_year,
    project_income_source_for_period,
    project_income_source_for_year,
)


def test_annualize_income_uses_supported_frequency_multipliers() -> None:
    amount = Decimal("100.00")

    assert annualize_income(amount, "weekly") == Decimal("5200.00")
    assert annualize_income(amount, "biweekly") == Decimal("2600.00")
    assert annualize_income(amount, "semimonthly") == Decimal("2400.00")
    assert annualize_income(amount, "monthly") == Decimal("1200.00")
    assert annualize_income(amount, "quarterly") == Decimal("400.00")
    assert annualize_income(amount, "annually") == Decimal("100.00")
    assert annualize_income(amount, "unknown") == Decimal("100.00")


def test_income_source_uses_default_growth_after_start_year() -> None:
    source = _source(
        amount=Decimal("1000.00"),
        frequency="monthly",
        start_date=date(2026, 7, 15),
        end_date=date(2027, 2, 10),
        growth_rate=None,
    )

    assert project_income_source_for_year(source, 2025) == Decimal("0.00")
    assert project_income_source_for_year(source, 2026) == Decimal("12000.00")
    assert project_income_source_for_year(source, 2027) == Decimal("12240.00")
    assert project_income_source_for_year(source, 2028) == Decimal("0.00")


def test_income_period_prorates_active_months_and_respects_end_date() -> None:
    source = _source(
        amount=Decimal("1000.00"),
        frequency="monthly",
        start_date=date(2026, 7, 15),
        end_date=date(2027, 2, 10),
        growth_rate=None,
    )

    assert project_income_source_for_period(
        source,
        date(2027, 1, 1),
        date(2027, 3, 31),
        3,
    ) == Decimal("2040.00")
    assert project_income_source_for_period(
        source,
        date(2027, 4, 1),
        date(2027, 6, 30),
        3,
    ) == Decimal("0.00")


def test_income_policy_aggregates_sources() -> None:
    sources = [
        _source(
            amount=Decimal("1000.00"),
            frequency="monthly",
            start_date=date(2026, 1, 1),
            end_date=None,
            growth_rate=Decimal("0.00"),
        ),
        _source(
            amount=Decimal("5000.00"),
            frequency="annually",
            start_date=date(2026, 1, 1),
            end_date=None,
            growth_rate=Decimal("0.00"),
        ),
    ]

    assert project_income_for_year(sources, 2026) == Decimal("17000.00")


def _source(
    *,
    amount: Decimal,
    frequency: str,
    start_date: date,
    end_date: date | None,
    growth_rate: Decimal | None,
) -> ProjectionIncomeSource:
    return ProjectionIncomeSource(
        amount=amount,
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
        growth_rate=growth_rate,
        deposit_account_id=None,
    )
