from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.analytics.projection_contracts import (
    ProjectionAccount,
    ProjectionLiquidationStrategy,
    ProjectionMortgage,
    ProjectionProperty,
    ProjectionPropertySale,
)
from app.analytics.projection_tax import property_sale_tax
from app.analytics.projection_withdrawals import (
    WithdrawalResult,
    liquidation_expense_rate,
)

TAXABLE_INVESTMENT_CATEGORIES = {"taxable_investment", "brokerage"}
ShortfallFunder = Callable[[Decimal], WithdrawalResult]


@dataclass(frozen=True)
class ProjectedPropertySale:
    property_account_id: UUID
    gross_sale_price: Decimal
    proceeds_account_id: UUID
    selling_expense_rate: Decimal | None
    estimated_tax_rate: Decimal


@dataclass
class AutomaticPropertySaleContext:
    strategies: Sequence[ProjectionLiquidationStrategy]
    fixed_sale_property_ids: set[UUID]
    mortgage_profiles_by_property: dict[UUID, ProjectionMortgage]
    property_profiles: dict[UUID, ProjectionProperty]
    sold_mortgage_account_ids: set[UUID]
    used_property_ids: set[UUID]
    as_of_date: date

    def next_strategy(
        self,
        accounts_by_id: dict[UUID, ProjectionAccount],
        balances: dict[UUID, Decimal],
    ) -> ProjectionLiquidationStrategy | None:
        eligible = [
            strategy
            for strategy in self.strategies
            if strategy.enabled
            and strategy.property_account_id not in self.fixed_sale_property_ids
            and strategy.property_account_id not in self.used_property_ids
            and (
                strategy.earliest_sale_date is None
                or strategy.earliest_sale_date <= self.as_of_date
            )
            and strategy.property_account_id in accounts_by_id
            and strategy.proceeds_account_id in accounts_by_id
            and balances[strategy.property_account_id] > Decimal("0.00")
        ]
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda strategy: (
                strategy.priority,
                accounts_by_id[strategy.property_account_id].name.lower(),
            ),
        )


def apply_property_sale(
    accounts_by_id: dict[UUID, ProjectionAccount],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    sale: ProjectionPropertySale | ProjectedPropertySale,
    property_profile: ProjectionProperty | None,
    mortgage_profile: ProjectionMortgage | None,
    sold_mortgage_account_ids: set[UUID],
    basis_balances: dict[UUID, Decimal] | None,
    fund_shortfall: ShortfallFunder,
) -> WithdrawalResult:
    """Apply all legs of a fixed or automatic property-sale transaction."""
    property_account = accounts_by_id.get(sale.property_account_id)
    proceeds_account = accounts_by_id.get(sale.proceeds_account_id)
    if property_account is None or proceeds_account is None:
        raise ValueError("Property sale accounts must be active accounts in the household")

    automatic_sale = isinstance(sale, ProjectedPropertySale)
    cash_flow_prefix = "automatic_property_sale" if automatic_sale else "property_sale"
    property_balance = max(balances[property_account.id], Decimal("0.00"))
    if property_balance != Decimal("0.00"):
        _record_account_cash_flow(
            balances,
            cash_flows,
            property_account,
            f"{cash_flow_prefix}_removal",
            -property_balance,
        )

    mortgage_payoff = Decimal("0.00")
    if mortgage_profile is not None:
        mortgage_account = accounts_by_id.get(mortgage_profile.liability_account_id)
        if mortgage_account is not None:
            mortgage_payoff = max(balances[mortgage_account.id], Decimal("0.00"))
            if mortgage_payoff != Decimal("0.00"):
                _record_account_cash_flow(
                    balances,
                    cash_flows,
                    mortgage_account,
                    "mortgage_payoff",
                    -mortgage_payoff,
                )
            sold_mortgage_account_ids.add(mortgage_account.id)

    selling_expense_rate = (
        sale.selling_expense_rate
        if sale.selling_expense_rate is not None
        else liquidation_expense_rate(property_account)
    )
    selling_expense = (sale.gross_sale_price * selling_expense_rate).quantize(Decimal("0.01"))
    if selling_expense != Decimal("0.00"):
        cash_flows.append(
            {
                "account_id": property_account.id,
                "account_name": property_account.name,
                "cash_flow_type": f"{cash_flow_prefix}_expense",
                "amount": -selling_expense,
            }
        )

    tax_basis = (
        property_profile.adjusted_tax_basis
        if property_profile is not None and property_profile.adjusted_tax_basis is not None
        else property_profile.purchase_price
        if property_profile is not None
        else None
    )
    estimated_sale_tax = property_sale_tax(
        sale.gross_sale_price,
        selling_expense,
        tax_basis,
        sale.estimated_tax_rate,
    )
    if estimated_sale_tax != Decimal("0.00"):
        cash_flows.append(
            {
                "account_id": property_account.id,
                "account_name": property_account.name,
                "cash_flow_type": f"{cash_flow_prefix}_tax",
                "amount": -estimated_sale_tax,
            }
        )

    net_proceeds = (
        sale.gross_sale_price - mortgage_payoff - selling_expense - estimated_sale_tax
    ).quantize(Decimal("0.01"))
    if net_proceeds >= Decimal("0.00"):
        if net_proceeds != Decimal("0.00"):
            if (
                basis_balances is not None
                and proceeds_account.category in TAXABLE_INVESTMENT_CATEGORIES
            ):
                basis_balances[proceeds_account.id] = (
                    basis_balances.get(proceeds_account.id, Decimal("0.00")) + net_proceeds
                ).quantize(Decimal("0.01"))
            _record_account_cash_flow(
                balances,
                cash_flows,
                proceeds_account,
                f"{cash_flow_prefix}_proceeds",
                net_proceeds,
            )
        return WithdrawalResult(
            liquidation_expenses=selling_expense,
            explicit_taxes=estimated_sale_tax,
        )

    shortfall_result = fund_shortfall(abs(net_proceeds))
    shortfall_result.liquidation_expenses = (
        shortfall_result.liquidation_expenses + selling_expense
    ).quantize(Decimal("0.01"))
    shortfall_result.explicit_taxes = (
        shortfall_result.explicit_taxes + estimated_sale_tax
    ).quantize(Decimal("0.01"))
    return shortfall_result


def ordered_march_sale_schedules(
    strategies: Sequence[ProjectionLiquidationStrategy],
    *,
    start_year: int,
    end_year: int,
    not_before: date,
) -> list[dict[UUID, date | None]]:
    schedules: list[dict[UUID, date | None]] = []

    def build(
        index: int,
        previous_date: date | None,
        previous_was_never: bool,
        schedule: dict[UUID, date | None],
    ) -> None:
        if index == len(strategies):
            schedules.append(dict(schedule))
            return
        strategy = strategies[index]
        if previous_was_never:
            choices: list[date | None] = [None]
        else:
            choices = [
                date(year, 3, 1)
                for year in range(start_year, end_year + 1)
                if date(year, 3, 1) >= not_before
                and (
                    strategy.earliest_sale_date is None
                    or date(year, 3, 1) >= strategy.earliest_sale_date
                )
                and (previous_date is None or date(year, 3, 1) >= previous_date)
            ]
            choices.append(None)
        for choice in choices:
            schedule[strategy.property_account_id] = choice
            build(index + 1, choice, choice is None, schedule)
        schedule.pop(strategy.property_account_id, None)

    build(0, None, False, {})
    return schedules


def _record_account_cash_flow(
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    account: ProjectionAccount,
    cash_flow_type: str,
    amount: Decimal,
) -> None:
    amount = amount.quantize(Decimal("0.01"))
    projected_balance = (balances[account.id] + amount).quantize(Decimal("0.01"))
    if projected_balance < Decimal("0.00"):
        raise ValueError(f"Projection cash flow would make account '{account.name}' negative")
    balances[account.id] = projected_balance
    cash_flows.append(
        {
            "account_id": account.id,
            "account_name": account.name,
            "cash_flow_type": cash_flow_type,
            "amount": amount,
        }
    )
