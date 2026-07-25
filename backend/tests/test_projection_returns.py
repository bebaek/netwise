from datetime import date
from decimal import Decimal
from uuid import UUID

from app.analytics.projection_contracts import ProjectionAccount, ProjectionProperty
from app.analytics.projection_returns import (
    annual_return_for_account,
    period_return,
    project_balance_with_return,
)


def test_return_policy_prefers_account_override_then_category_default() -> None:
    explicit = _account(
        1,
        category="checking",
        expected_annual_yield=Decimal("0.080000"),
    )
    savings = _account(2, category="savings")
    other = _account(3, category="collectible", liquidity_class="illiquid")

    assert annual_return_for_account(explicit, None) == Decimal("0.080000")
    assert annual_return_for_account(savings, None) == Decimal("0.020000")
    assert annual_return_for_account(other, None) == Decimal("0.030000")


def test_real_estate_return_uses_property_appreciation_or_zero() -> None:
    account = _account(
        1,
        category="real_estate",
        liquidity_class="illiquid",
        expected_annual_yield=Decimal("0.250000"),
    )
    profile = _property(account.id, Decimal("0.040000"))

    assert annual_return_for_account(account, profile) == Decimal("0.040000")
    assert annual_return_for_account(account, None) == Decimal("0.000000")
    assert annual_return_for_account(account, _property(account.id, None)) == Decimal("0.000000")


def test_liability_without_override_has_zero_return() -> None:
    liability = _account(
        1,
        account_kind="liability",
        category="other_debt",
        liquidity_class="debt",
    )

    assert annual_return_for_account(liability, None) == Decimal("0.000000")


def test_return_policy_converts_effective_annual_return_and_projects_balance() -> None:
    annual_return = Decimal("0.120000")

    assert period_return(annual_return, 12) == annual_return
    assert period_return(annual_return, 3) == Decimal("0.028737344722080280425421384")
    assert project_balance_with_return(Decimal("1000.00"), annual_return, 3) == Decimal("1028.74")


def _account(
    account_id: int,
    *,
    category: str,
    liquidity_class: str = "liquid",
    account_kind: str = "asset",
    expected_annual_yield: Decimal | None = None,
) -> ProjectionAccount:
    return ProjectionAccount(
        id=UUID(int=account_id),
        name=f"Account {account_id}",
        account_kind=account_kind,
        category=category,
        liquidity_class=liquidity_class,
        retirement_tax_treatment=None,
        expected_annual_yield=expected_annual_yield,
        liquidation_expense_rate=None,
    )


def _property(
    account_id: UUID,
    expected_appreciation_rate: Decimal | None,
) -> ProjectionProperty:
    return ProjectionProperty(
        account_id=account_id,
        purchase_date=date(2020, 1, 1),
        purchase_price=None,
        adjusted_tax_basis=None,
        expected_appreciation_rate=expected_appreciation_rate,
        property_tax_annual=None,
        insurance_annual=None,
        tax_and_insurance_annual=None,
        maintenance_rate=None,
        hoa_monthly=None,
        is_rental=False,
        rental_start_date=None,
        monthly_market_rent=None,
        other_monthly_income=None,
        rent_growth_rate=None,
        vacancy_rate=None,
        management_fee_rate=None,
        utilities_annual=None,
        other_operating_expense_annual=None,
        capital_reserve_rate=None,
        rental_deposit_account_id=None,
    )
