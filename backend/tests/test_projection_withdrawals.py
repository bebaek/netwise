from decimal import Decimal
from uuid import UUID

from app.analytics.projection_contracts import ProjectionAccount
from app.analytics.projection_withdrawals import (
    withdrawal_order,
    withdraw_from_account_pool,
)


def _account(
    account_id: int,
    name: str,
    category: str,
    liquidity_class: str,
    *,
    retirement_tax_treatment: str | None = None,
    liquidation_expense_rate: Decimal | None = None,
    account_kind: str = "asset",
) -> ProjectionAccount:
    return ProjectionAccount(
        id=UUID(int=account_id),
        name=name,
        account_kind=account_kind,
        category=category,
        liquidity_class=liquidity_class,
        retirement_tax_treatment=retirement_tax_treatment,
        expected_annual_yield=None,
        liquidation_expense_rate=liquidation_expense_rate,
    )


def test_withdrawal_order_uses_default_priority_and_preferred_cutoff() -> None:
    checking = _account(1, "Checking", "checking", "cash")
    savings = _account(2, "Emergency Fund", "savings", "liquid")
    brokerage = _account(3, "Brokerage", "brokerage", "marketable")
    stock = _account(6, "Vanguard Stock", "taxable_investment", "marketable")
    roth = _account(
        4,
        "Roth IRA",
        "retirement",
        "retirement_liquid",
        retirement_tax_treatment="roth",
    )
    traditional = _account(
        5,
        "401k",
        "retirement",
        "retirement_liquid",
        retirement_tax_treatment="traditional",
    )
    second_traditional = _account(
        7,
        "Fidelity",
        "retirement",
        "retirement_liquid",
        retirement_tax_treatment="traditional",
    )
    accounts = [traditional, brokerage, checking, roth, savings, stock, second_traditional]
    accounts_by_id = {account.id: account for account in accounts}

    assert [account.name for account in withdrawal_order(accounts, accounts_by_id, None)] == [
        "Checking",
        "Emergency Fund",
        "Brokerage",
        "Vanguard Stock",
        "Roth IRA",
        "401k",
        "Fidelity",
    ]
    assert [
        account.name for account in withdrawal_order(accounts, accounts_by_id, brokerage.id)
    ] == ["Brokerage", "Vanguard Stock", "Roth IRA", "401k", "Fidelity"]


def test_withdrawal_policy_tracks_capital_gains_basis_and_liquidation_cost() -> None:
    brokerage = _account(1, "Brokerage", "brokerage", "marketable")
    balances = {brokerage.id: Decimal("1000.00")}
    basis_balances = {brokerage.id: Decimal("600.00")}
    cash_flows: list[dict] = []

    result = withdraw_from_account_pool(
        [brokerage],
        {brokerage.id: brokerage},
        balances,
        cash_flows,
        Decimal("100.00"),
        "spending",
        None,
        Decimal("0.25"),
        basis_balances,
    )

    assert result.net_amount == Decimal("100.00")
    assert result.capital_gains_tax == Decimal("6.45")
    assert result.taxable_amount == Decimal("0.00")
    assert result.liquidation_expenses == Decimal("1.08")
    assert result.unfunded_amount == Decimal("0.00")
    assert balances[brokerage.id] == Decimal("892.47")
    assert basis_balances[brokerage.id] == Decimal("535.48")
    assert [(flow["cash_flow_type"], flow["amount"]) for flow in cash_flows] == [
        ("spending", Decimal("-100.00")),
        ("tax_payment", Decimal("-6.45")),
        ("liquidation_expense", Decimal("-1.08")),
    ]


def test_roth_withdrawal_is_tax_free_and_reports_unfunded_amount() -> None:
    roth = _account(
        1,
        "Roth IRA",
        "retirement",
        "retirement_liquid",
        retirement_tax_treatment="roth",
    )
    balances = {roth.id: Decimal("40.00")}
    cash_flows: list[dict] = []

    result = withdraw_from_account_pool(
        [roth],
        {roth.id: roth},
        balances,
        cash_flows,
        Decimal("50.00"),
        "spending",
        None,
        Decimal("0.25"),
    )

    assert result.net_amount == Decimal("40.00")
    assert result.taxable_amount == Decimal("0.00")
    assert result.capital_gains_tax == Decimal("0.00")
    assert result.unfunded_amount == Decimal("10.00")
    assert balances[roth.id] == Decimal("0.00")
    assert [flow["cash_flow_type"] for flow in cash_flows] == ["spending"]
