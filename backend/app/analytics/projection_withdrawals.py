from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal
from uuid import UUID

from app.analytics.projection_contracts import ProjectionAccount

DEFAULT_CAPITAL_GAINS_TAX_RATE = Decimal("0.150000")
DEFAULT_LIQUIDATION_EXPENSE_RATES = {
    "taxable_investment": Decimal("0.010000"),
    "brokerage": Decimal("0.010000"),
    "real_estate": Decimal("0.060000"),
}
BANK_CATEGORIES = {"cash", "checking", "savings"}
LIQUIDITY_CLASSES = {"cash", "liquid", "marketable", "retirement_liquid"}
DEFAULT_FUNDING_ACCOUNT_NAMES = {"checking"}


@dataclass
class WithdrawalResult:
    net_amount: Decimal = Decimal("0.00")
    taxable_amount: Decimal = Decimal("0.00")
    capital_gains_tax: Decimal = Decimal("0.00")
    liquidation_expenses: Decimal = Decimal("0.00")
    explicit_taxes: Decimal = Decimal("0.00")
    unfunded_amount: Decimal = Decimal("0.00")

    def add(self, other: "WithdrawalResult") -> None:
        self.net_amount = (self.net_amount + other.net_amount).quantize(Decimal("0.01"))
        self.taxable_amount = (self.taxable_amount + other.taxable_amount).quantize(Decimal("0.01"))
        self.capital_gains_tax = (self.capital_gains_tax + other.capital_gains_tax).quantize(
            Decimal("0.01")
        )
        self.liquidation_expenses = (
            self.liquidation_expenses + other.liquidation_expenses
        ).quantize(Decimal("0.01"))
        self.explicit_taxes = (self.explicit_taxes + other.explicit_taxes).quantize(Decimal("0.01"))
        self.unfunded_amount = (self.unfunded_amount + other.unfunded_amount).quantize(
            Decimal("0.01")
        )


def withdraw_from_account_pool(
    accounts: Sequence[ProjectionAccount],
    accounts_by_id: dict[UUID, ProjectionAccount],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    amount: Decimal,
    cash_flow_type: str,
    preferred_account_id: UUID | None,
    tax_rate: Decimal,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> WithdrawalResult:
    """Fund a net amount from eligible assets in deterministic priority order."""
    remaining_net = amount.quantize(Decimal("0.01"))
    result = WithdrawalResult()
    if remaining_net == Decimal("0.00"):
        return result

    asset_accounts = [account for account in accounts if account.account_kind == "asset"]
    if not asset_accounts:
        result.unfunded_amount = remaining_net
        return result

    effective_preference = (
        preferred_account_id
        if any(account.id == preferred_account_id for account in asset_accounts)
        else None
    )
    ordered_accounts = withdrawal_order(asset_accounts, accounts_by_id, effective_preference)
    for account in ordered_accounts:
        available = max(balances[account.id], Decimal("0.00"))
        if available == Decimal("0.00"):
            continue

        taxes_apply = withdrawal_has_tax_consequences(account)
        has_basis_tracking = (
            basis_balances is not None
            and account.id in basis_balances
            and available > Decimal("0.00")
        )
        capital_gain_fraction = Decimal("0.00")
        if has_basis_tracking:
            effective_tax_rate = DEFAULT_CAPITAL_GAINS_TAX_RATE
            basis = max(basis_balances[account.id], Decimal("0.00"))
            capital_gain_fraction = max(available - basis, Decimal("0.00")) / available
        else:
            effective_tax_rate = tax_rate if taxes_apply else Decimal("0.00")
        expense_rate = liquidation_expense_rate(account)
        if has_basis_tracking:
            drag_rate = (effective_tax_rate * capital_gain_fraction) + expense_rate
        else:
            drag_rate = effective_tax_rate + expense_rate
        if drag_rate >= Decimal("1.00"):
            continue

        gross_needed = (remaining_net / (Decimal("1.00") - drag_rate)).quantize(
            Decimal("0.01"), rounding=ROUND_UP
        )
        gross_deduction = min(available, gross_needed)
        if gross_deduction == Decimal("0.00"):
            continue

        if has_basis_tracking:
            taxable_portion = (gross_deduction * capital_gain_fraction).quantize(Decimal("0.01"))
        else:
            taxable_portion = gross_deduction if taxes_apply else Decimal("0.00")
        tax_amount = (taxable_portion * effective_tax_rate).quantize(Decimal("0.01"))
        liquidation_expense = (gross_deduction * expense_rate).quantize(Decimal("0.01"))
        net_amount = (gross_deduction - tax_amount - liquidation_expense).quantize(Decimal("0.01"))
        if net_amount == Decimal("0.00"):
            continue

        _record_account_cash_flow(balances, cash_flows, account, cash_flow_type, -net_amount)
        if tax_amount != Decimal("0.00"):
            _record_account_cash_flow(balances, cash_flows, account, "tax_payment", -tax_amount)
        if liquidation_expense != Decimal("0.00"):
            _record_account_cash_flow(
                balances,
                cash_flows,
                account,
                "liquidation_expense",
                -liquidation_expense,
            )
        if has_basis_tracking:
            basis_balances[account.id] = max(
                basis_balances[account.id]
                - (gross_deduction * (Decimal("1.00") - capital_gain_fraction)),
                Decimal("0.00"),
            ).quantize(Decimal("0.01"))

        result.net_amount = (result.net_amount + net_amount).quantize(Decimal("0.01"))
        if has_basis_tracking:
            result.capital_gains_tax = (result.capital_gains_tax + tax_amount).quantize(
                Decimal("0.01")
            )
        elif taxes_apply:
            result.taxable_amount = (result.taxable_amount + taxable_portion).quantize(
                Decimal("0.01")
            )
        result.liquidation_expenses = (result.liquidation_expenses + liquidation_expense).quantize(
            Decimal("0.01")
        )
        remaining_net = (remaining_net - net_amount).quantize(Decimal("0.01"))
        if remaining_net <= Decimal("0.00"):
            return result

    result.unfunded_amount = remaining_net
    return result


def withdrawal_order(
    asset_accounts: Sequence[ProjectionAccount],
    accounts_by_id: dict[UUID, ProjectionAccount],
    preferred_account_id: UUID | None,
) -> list[ProjectionAccount]:
    ordered_accounts = sorted(
        (account for account in asset_accounts if funding_priority(account) is not None),
        key=funding_priority,
    )
    if preferred_account_id is None:
        return ordered_accounts
    preferred_account = accounts_by_id[preferred_account_id]
    if funding_priority(preferred_account) is None:
        return [preferred_account] + [
            account for account in ordered_accounts if account.id != preferred_account_id
        ]
    preferred_index = next(
        index
        for index, account in enumerate(ordered_accounts)
        if account.id == preferred_account_id
    )
    return ordered_accounts[preferred_index:]


def funding_priority(account: ProjectionAccount) -> tuple[int, str] | None:
    account_name = account.name.casefold()
    if account_name in DEFAULT_FUNDING_ACCOUNT_NAMES:
        return (0, account_name)
    if account.category in BANK_CATEGORIES:
        return (1, account_name)
    if (
        account.category in {"taxable_investment", "brokerage"}
        and account.liquidity_class in LIQUIDITY_CLASSES
    ):
        return (2, account_name)
    if account.category == "retirement" and account.retirement_tax_treatment == "roth":
        return (3, account_name)
    if account.category == "retirement" and account.liquidity_class in LIQUIDITY_CLASSES:
        return (4, account_name)
    if account.category != "real_estate" and account.liquidity_class in LIQUIDITY_CLASSES:
        return (5, account_name)
    return None


def withdrawal_has_tax_consequences(account: ProjectionAccount) -> bool:
    if account.category in BANK_CATEGORIES:
        return False
    if account.category == "retirement" and account.retirement_tax_treatment == "roth":
        return False
    return True


def liquidation_expense_rate(account: ProjectionAccount) -> Decimal:
    if account.liquidation_expense_rate is not None:
        return account.liquidation_expense_rate
    return DEFAULT_LIQUIDATION_EXPENSE_RATES.get(account.category, Decimal("0.000000"))


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
