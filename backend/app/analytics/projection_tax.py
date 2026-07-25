from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from app.analytics.projection_contracts import (
    ProjectionAccount,
    ProjectionLiquidationStrategy,
    ProjectionProperty,
    ProjectionPropertySale,
)
from app.analytics.projection_withdrawals import WithdrawalResult


def taxable_income_for_period(
    projected_income: Decimal,
    projected_rental_income: Decimal,
    projected_rental_expenses: Decimal,
) -> Decimal:
    return max(
        projected_income + projected_rental_income - projected_rental_expenses,
        Decimal("0.00"),
    )


def effective_income_tax(taxable_income: Decimal, tax_rate: Decimal) -> Decimal:
    return (taxable_income * tax_rate).quantize(Decimal("0.01"))


def withdrawal_taxes(result: WithdrawalResult, tax_rate: Decimal) -> Decimal:
    ordinary_tax = (result.taxable_amount * tax_rate).quantize(Decimal("0.01"))
    return (ordinary_tax + result.capital_gains_tax + result.explicit_taxes).quantize(
        Decimal("0.01")
    )


def property_sale_tax(
    gross_sale_price: Decimal,
    selling_expense: Decimal,
    tax_basis: Decimal | None,
    estimated_tax_rate: Decimal,
) -> Decimal:
    taxable_gain = (
        max(gross_sale_price - selling_expense - tax_basis, Decimal("0.00"))
        if tax_basis is not None
        else gross_sale_price
    )
    return (taxable_gain * estimated_tax_rate).quantize(Decimal("0.01"))


def property_sale_tax_basis_warnings(
    accounts_by_id: dict[UUID, ProjectionAccount],
    property_profiles: dict[UUID, ProjectionProperty],
    real_estate_sales: Sequence[ProjectionPropertySale],
    automatic_sale_strategies: Sequence[ProjectionLiquidationStrategy],
) -> list[str]:
    property_ids = {
        sale.property_account_id
        for sale in real_estate_sales
        if sale.estimated_tax_rate > Decimal("0.00")
    } | {
        strategy.property_account_id
        for strategy in automatic_sale_strategies
        if strategy.enabled and strategy.estimated_tax_rate > Decimal("0.00")
    }
    warnings = []
    for property_id in sorted(
        property_ids,
        key=lambda item: (
            accounts_by_id[item].name.casefold() if item in accounts_by_id else str(item)
        ),
    ):
        account = accounts_by_id.get(property_id)
        profile = property_profiles.get(property_id)
        property_name = account.name if account is not None else str(property_id)
        if profile is None or (
            profile.adjusted_tax_basis is None and profile.purchase_price is None
        ):
            warnings.append(
                f"{property_name}: sale tax uses the gross-price fallback because tax basis is missing."
            )
    return warnings
