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
from app.analytics.projection_property_sales import (
    AutomaticPropertySaleContext,
    ProjectedPropertySale,
    apply_property_sale,
    ordered_march_sale_schedules,
)
from app.analytics.projection_withdrawals import WithdrawalResult


def test_property_sale_applies_transaction_legs_and_tracks_proceeds_basis() -> None:
    home = _account(1, "Home", "real_estate", "illiquid")
    mortgage = _account(2, "Mortgage", "mortgage", "debt", account_kind="liability")
    brokerage = _account(3, "Brokerage", "brokerage", "marketable")
    accounts_by_id = {account.id: account for account in (home, mortgage, brokerage)}
    balances = {
        home.id: Decimal("500000.00"),
        mortgage.id: Decimal("300000.00"),
        brokerage.id: Decimal("0.00"),
    }
    basis_balances = {brokerage.id: Decimal("0.00")}
    cash_flows: list[dict] = []
    sold_mortgages: set[UUID] = set()
    shortfalls: list[Decimal] = []

    result = apply_property_sale(
        accounts_by_id,
        balances,
        cash_flows,
        ProjectionPropertySale(
            property_account_id=home.id,
            sale_date=date(2026, 6, 1),
            gross_sale_price=Decimal("500000.00"),
            proceeds_account_id=brokerage.id,
            selling_expense_rate=Decimal("0.100000"),
            estimated_tax_rate=Decimal("0.150000"),
        ),
        _property(home.id, adjusted_tax_basis=Decimal("300000.00")),
        _mortgage(mortgage.id, home.id),
        sold_mortgages,
        basis_balances,
        lambda amount: _unexpected_shortfall(amount, shortfalls),
    )

    assert balances == {
        home.id: Decimal("0.00"),
        mortgage.id: Decimal("0.00"),
        brokerage.id: Decimal("127500.00"),
    }
    assert basis_balances[brokerage.id] == Decimal("127500.00")
    assert sold_mortgages == {mortgage.id}
    assert shortfalls == []
    assert result.liquidation_expenses == Decimal("50000.00")
    assert result.explicit_taxes == Decimal("22500.00")
    assert [flow["cash_flow_type"] for flow in cash_flows] == [
        "property_sale_removal",
        "mortgage_payoff",
        "property_sale_expense",
        "property_sale_tax",
        "property_sale_proceeds",
    ]


def test_automatic_property_sale_delegates_shortfall_funding() -> None:
    home = _account(1, "Home", "real_estate", "illiquid")
    mortgage = _account(2, "Mortgage", "mortgage", "debt", account_kind="liability")
    checking = _account(3, "Checking", "checking", "liquid")
    accounts_by_id = {account.id: account for account in (home, mortgage, checking)}
    balances = {
        home.id: Decimal("100000.00"),
        mortgage.id: Decimal("150000.00"),
        checking.id: Decimal("50000.00"),
    }
    cash_flows: list[dict] = []
    funded: list[Decimal] = []

    def fund_shortfall(amount: Decimal) -> WithdrawalResult:
        funded.append(amount)
        balances[checking.id] -= amount
        return WithdrawalResult(net_amount=amount)

    result = apply_property_sale(
        accounts_by_id,
        balances,
        cash_flows,
        ProjectedPropertySale(
            property_account_id=home.id,
            gross_sale_price=Decimal("100000.00"),
            proceeds_account_id=checking.id,
            selling_expense_rate=Decimal("0.000000"),
            estimated_tax_rate=Decimal("0.000000"),
        ),
        None,
        _mortgage(mortgage.id, home.id),
        set(),
        None,
        fund_shortfall,
    )

    assert funded == [Decimal("50000.00")]
    assert balances[checking.id] == Decimal("0.00")
    assert result.net_amount == Decimal("50000.00")
    assert cash_flows[0]["cash_flow_type"] == "automatic_property_sale_removal"


def test_automatic_sale_context_selects_eligible_strategy_by_priority() -> None:
    first = _account(1, "First Property", "real_estate", "illiquid")
    second = _account(2, "Second Property", "real_estate", "illiquid")
    proceeds = _account(3, "Checking", "checking", "liquid")
    first_strategy = _strategy(first.id, proceeds.id, priority=20)
    second_strategy = _strategy(second.id, proceeds.id, priority=10)
    context = AutomaticPropertySaleContext(
        strategies=[first_strategy, second_strategy],
        fixed_sale_property_ids=set(),
        mortgage_profiles_by_property={},
        property_profiles={},
        sold_mortgage_account_ids=set(),
        used_property_ids=set(),
        as_of_date=date(2026, 6, 1),
    )
    accounts_by_id = {account.id: account for account in (first, second, proceeds)}

    assert (
        context.next_strategy(
            accounts_by_id,
            {first.id: Decimal("100.00"), second.id: Decimal("100.00")},
        )
        == second_strategy
    )
    context.used_property_ids.add(second.id)
    assert (
        context.next_strategy(
            accounts_by_id,
            {first.id: Decimal("100.00"), second.id: Decimal("100.00")},
        )
        == first_strategy
    )


def test_sale_schedule_respects_current_date_and_strategy_earliest_date() -> None:
    proceeds_id = UUID(int=3)
    strategy = _strategy(
        UUID(int=1),
        proceeds_id,
        priority=1,
        earliest_sale_date=date(2027, 1, 1),
    )

    assert ordered_march_sale_schedules(
        [strategy],
        start_year=2026,
        end_year=2027,
        not_before=date(2026, 7, 1),
    ) == [
        {strategy.property_account_id: date(2027, 3, 1)},
        {strategy.property_account_id: None},
    ]


def _unexpected_shortfall(amount: Decimal, shortfalls: list[Decimal]) -> WithdrawalResult:
    shortfalls.append(amount)
    return WithdrawalResult(unfunded_amount=amount)


def _account(
    account_id: int,
    name: str,
    category: str,
    liquidity_class: str,
    *,
    account_kind: str = "asset",
) -> ProjectionAccount:
    return ProjectionAccount(
        id=UUID(int=account_id),
        name=name,
        account_kind=account_kind,
        category=category,
        liquidity_class=liquidity_class,
        retirement_tax_treatment=None,
        expected_annual_yield=None,
        liquidation_expense_rate=None,
    )


def _mortgage(liability_id: UUID, property_id: UUID) -> ProjectionMortgage:
    return ProjectionMortgage(
        liability_account_id=liability_id,
        property_account_id=property_id,
        original_principal=Decimal("300000.00"),
        interest_rate=Decimal("0.040000"),
        term_months=360,
        start_date=date(2020, 1, 1),
        monthly_payment=None,
    )


def _property(
    account_id: UUID,
    *,
    adjusted_tax_basis: Decimal | None,
) -> ProjectionProperty:
    return ProjectionProperty(
        account_id=account_id,
        purchase_date=None,
        purchase_price=None,
        adjusted_tax_basis=adjusted_tax_basis,
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


def _strategy(
    property_id: UUID,
    proceeds_id: UUID,
    *,
    priority: int,
    earliest_sale_date: date | None = None,
) -> ProjectionLiquidationStrategy:
    return ProjectionLiquidationStrategy(
        property_account_id=property_id,
        enabled=True,
        optimization_mode="liquidity_shortfall",
        priority=priority,
        earliest_sale_date=earliest_sale_date,
        proceeds_account_id=proceeds_id,
        selling_expense_rate=None,
        estimated_tax_rate=Decimal("0.150000"),
    )
