from datetime import date
from decimal import Decimal
from uuid import UUID

from app.analytics.projection_contracts import (
    ProjectionAccount,
    ProjectionProperty,
    ProjectionPropertySale,
)
from app.analytics.projection_tax import (
    effective_income_tax,
    property_sale_tax,
    property_sale_tax_basis_warnings,
    taxable_income_for_period,
    withdrawal_taxes,
)
from app.analytics.projection_withdrawals import WithdrawalResult


def test_taxable_income_nets_rental_expenses_and_clamps_at_zero() -> None:
    assert taxable_income_for_period(
        Decimal("100000.00"),
        Decimal("12000.00"),
        Decimal("20000.00"),
    ) == Decimal("92000.00")
    assert taxable_income_for_period(
        Decimal("0.00"),
        Decimal("5000.00"),
        Decimal("6000.00"),
    ) == Decimal("0.00")


def test_effective_income_and_withdrawal_taxes_preserve_tax_components() -> None:
    assert effective_income_tax(Decimal("92000.00"), Decimal("0.225000")) == Decimal("20700.00")

    result = WithdrawalResult(
        taxable_amount=Decimal("1000.00"),
        capital_gains_tax=Decimal("75.00"),
        explicit_taxes=Decimal("25.00"),
    )
    assert withdrawal_taxes(result, Decimal("0.200000")) == Decimal("300.00")


def test_property_sale_tax_uses_net_gain_or_gross_fallback() -> None:
    assert property_sale_tax(
        Decimal("500000.00"),
        Decimal("50000.00"),
        Decimal("300000.00"),
        Decimal("0.150000"),
    ) == Decimal("22500.00")
    assert property_sale_tax(
        Decimal("500000.00"),
        Decimal("50000.00"),
        None,
        Decimal("0.150000"),
    ) == Decimal("75000.00")
    assert property_sale_tax(
        Decimal("500000.00"),
        Decimal("50000.00"),
        Decimal("600000.00"),
        Decimal("0.150000"),
    ) == Decimal("0.00")


def test_property_sale_tax_warning_requires_missing_basis_and_positive_tax_rate() -> None:
    property_id = UUID(int=1)
    account = _account(property_id, "Home")
    sale = ProjectionPropertySale(
        property_account_id=property_id,
        sale_date=date(2030, 1, 1),
        gross_sale_price=Decimal("500000.00"),
        proceeds_account_id=UUID(int=2),
        selling_expense_rate=None,
        estimated_tax_rate=Decimal("0.150000"),
    )

    assert property_sale_tax_basis_warnings(
        {property_id: account},
        {},
        [sale],
        [],
    ) == ["Home: sale tax uses the gross-price fallback because tax basis is missing."]
    assert (
        property_sale_tax_basis_warnings(
            {property_id: account},
            {property_id: _property(property_id, purchase_price=Decimal("300000.00"))},
            [sale],
            [],
        )
        == []
    )


def _account(account_id: UUID, name: str) -> ProjectionAccount:
    return ProjectionAccount(
        id=account_id,
        name=name,
        account_kind="asset",
        category="real_estate",
        liquidity_class="illiquid",
        retirement_tax_treatment=None,
        expected_annual_yield=None,
        liquidation_expense_rate=None,
    )


def _property(account_id: UUID, *, purchase_price: Decimal | None) -> ProjectionProperty:
    return ProjectionProperty(
        account_id=account_id,
        purchase_date=None,
        purchase_price=purchase_price,
        adjusted_tax_basis=None,
        expected_appreciation_rate=None,
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
