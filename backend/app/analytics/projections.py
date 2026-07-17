from dataclasses import dataclass
from datetime import date
from decimal import ROUND_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.mortgage import estimate_mortgage_balance
from app.db.models import (
    Account,
    AccountEvent,
    AccountEventType,
    AccountKind,
    AnnualTaxRecord,
    BalanceSnapshot,
    IncomeFrequency,
    IncomeSource,
    MortgageProfile,
    ProjectionBehavior,
    ProjectionSettings,
    RealEstateProperty,
    RealEstateSale,
)

DEFAULT_CATEGORY_YIELDS = {
    "cash": Decimal("0.010000"),
    "checking": Decimal("0.010000"),
    "savings": Decimal("0.020000"),
    "taxable_investment": Decimal("0.050000"),
    "brokerage": Decimal("0.050000"),
    "retirement": Decimal("0.050000"),
    "real_estate": Decimal("0.030000"),
    "mortgage": Decimal("0.000000"),
    "credit_card": Decimal("0.000000"),
}
DEFAULT_SPENDING_INFLATION_RATE = Decimal("0.030000")
DEFAULT_INCOME_GROWTH_RATE = Decimal("0.020000")

DEFAULT_LIQUIDATION_EXPENSE_RATES = {
    "taxable_investment": Decimal("0.010000"),
    "brokerage": Decimal("0.010000"),
    "retirement": Decimal("0.100000"),
    "real_estate": Decimal("0.060000"),
}


@dataclass
class WithdrawalResult:
    net_amount: Decimal = Decimal("0.00")
    taxable_amount: Decimal = Decimal("0.00")
    liquidation_expenses: Decimal = Decimal("0.00")

    def add(self, other: "WithdrawalResult") -> None:
        self.net_amount = (self.net_amount + other.net_amount).quantize(Decimal("0.01"))
        self.taxable_amount = (self.taxable_amount + other.taxable_amount).quantize(
            Decimal("0.01")
        )
        self.liquidation_expenses = (
            self.liquidation_expenses + other.liquidation_expenses
        ).quantize(Decimal("0.01"))


CASH_FLOW_CATEGORY_PRIORITY = {
    "cash": 0,
    "checking": 0,
    "savings": 1,
    "taxable_investment": 2,
    "brokerage": 2,
    "retirement": 3,
}

BANK_CATEGORIES = {"cash", "checking", "savings"}
LIQUIDITY_CLASSES = {"cash", "liquid", "marketable", "retirement_liquid"}

# Default withdrawal sequence: checking, taxable investments, Roth retirement,
# then other retirement accounts. Remaining eligible liquid accounts are fallbacks.
DEFAULT_FUNDING_ACCOUNT_NAMES = {"checking"}


AccountEventOutflowTypes = {
    AccountEventType.withdrawal,
    AccountEventType.large_purchase,
    AccountEventType.tax_payment,
    AccountEventType.account_removed,
}
AccountEventInflowTypes = {
    AccountEventType.contribution,
    AccountEventType.asset_sale,
    AccountEventType.gift,
    AccountEventType.inheritance,
    AccountEventType.account_added,
}


def calculate_net_worth_projection(
    db: Session,
    household_id: UUID,
    *,
    start_year: int,
    end_year: int,
    annual_spending: Decimal | None = None,
    spending_inflation_rate: Decimal | None = None,
    spending_account_id: UUID | None = None,
    tax_account_id: UUID | None = None,
) -> dict:
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    accounts = list(
        db.scalars(
            select(Account)
            .where(Account.household_id == household_id, Account.is_active.is_(True))
            .order_by(Account.name)
        ).all()
    )
    start_date = date(start_year, 1, 1)
    balances = {
        account.id: _latest_balance_on_or_before(db, account.id, start_date) or Decimal("0.00")
        for account in accounts
    }
    mortgage_profiles = {
        profile.liability_account_id: profile
        for profile in db.scalars(
            select(MortgageProfile).where(MortgageProfile.household_id == household_id)
        ).all()
    }
    property_profiles = {
        profile.account_id: profile
        for profile in db.scalars(
            select(RealEstateProperty).where(RealEstateProperty.household_id == household_id)
        ).all()
    }
    real_estate_sales = list(
        db.scalars(
            select(RealEstateSale)
            .where(
                RealEstateSale.household_id == household_id,
                RealEstateSale.sale_date >= start_date,
                RealEstateSale.sale_date <= date(end_year, 12, 31),
            )
            .order_by(RealEstateSale.sale_date)
        ).all()
    )
    mortgage_profiles_by_property = {
        profile.property_account_id: profile
        for profile in mortgage_profiles.values()
        if profile.property_account_id is not None
    }
    projection_events = list(
        db.scalars(
            select(AccountEvent)
            .where(
                AccountEvent.household_id == household_id,
                AccountEvent.projection_behavior != ProjectionBehavior.historical_only,
                AccountEvent.event_date >= start_date,
                AccountEvent.event_date <= date(end_year, 12, 31),
            )
            .order_by(AccountEvent.event_date)
        ).all()
    )
    income_sources = list(
        db.scalars(select(IncomeSource).where(IncomeSource.household_id == household_id)).all()
    )
    projection_settings = db.scalars(
        select(ProjectionSettings).where(ProjectionSettings.household_id == household_id)
    ).first()
    effective_annual_spending = (
        annual_spending
        if annual_spending is not None
        else projection_settings.annual_spending
        if projection_settings is not None
        else None
    )
    effective_spending_inflation_rate = (
        spending_inflation_rate
        if spending_inflation_rate is not None
        else projection_settings.spending_inflation_rate
        if projection_settings is not None
        and projection_settings.spending_inflation_rate is not None
        else DEFAULT_SPENDING_INFLATION_RATE
    )
    effective_spending_account_id = (
        spending_account_id
        if spending_account_id is not None
        else projection_settings.spending_account_id
        if projection_settings is not None
        else None
    )
    effective_tax_account_id = (
        tax_account_id
        if tax_account_id is not None
        else projection_settings.tax_account_id
        if projection_settings is not None
        else None
    )
    accounts_by_id = {account.id: account for account in accounts}
    _validate_cash_flow_account(accounts_by_id, effective_spending_account_id, "Spending account")
    _validate_cash_flow_account(accounts_by_id, effective_tax_account_id, "Tax account")
    for income_source in income_sources:
        _validate_cash_flow_account(
            accounts_by_id, income_source.deposit_account_id, "Income deposit account"
        )
    spending_baseline = (
        (start_year, effective_annual_spending.quantize(Decimal("0.01")))
        if effective_annual_spending is not None
        else None
    )
    tax_rate = _latest_effective_tax_rate(db, household_id)

    points = []
    sold_mortgage_account_ids: set[UUID] = set()
    for year in range(start_year, end_year + 1):
        as_of_date = date(year, 12, 31)
        year_start = date(year, 1, 1)

        for account in accounts:
            if account.id in mortgage_profiles:
                if account.id in sold_mortgage_account_ids:
                    balances[account.id] = Decimal("0.00")
                    continue
                balances[account.id] = estimate_mortgage_balance(
                    mortgage_profiles[account.id], as_of_date
                )
                continue

            annual_yield = _yield_for_account(account, property_profiles.get(account.id))
            balances[account.id] = (balances[account.id] * (Decimal("1") + annual_yield)).quantize(
                Decimal("0.01")
            )

        cash_flows = []
        withdrawal_result = WithdrawalResult()
        year_operations = [
            (sale.sale_date, 0, sale)
            for sale in real_estate_sales
            if year_start <= sale.sale_date <= as_of_date
        ] + [
            (event.event_date, 1, event)
            for event in projection_events
            if year_start <= event.event_date <= as_of_date
        ]
        for _, operation_kind, operation in sorted(year_operations, key=lambda item: (item[0], item[1])):
            if operation_kind == 0:
                withdrawal_result.add(
                    _apply_real_estate_sale(
                        accounts,
                        accounts_by_id,
                        balances,
                        cash_flows,
                        operation,
                        mortgage_profiles_by_property.get(operation.property_account_id),
                        sold_mortgage_account_ids,
                        tax_rate,
                    )
                )
            else:
                withdrawal_result.add(
                    _apply_projection_event(
                        accounts_by_id, balances, cash_flows, operation, tax_rate
                    )
                )

        projected_income = Decimal("0.00")
        for income_source in income_sources:
            income_amount = _projected_income_source_for_year(income_source, year)
            projected_income += income_amount
            if income_amount != Decimal("0.00"):
                target_account = _cash_flow_target_account(
                    accounts, accounts_by_id, income_source.deposit_account_id
                )
                if target_account is not None:
                    _apply_account_cash_flow(
                        balances, cash_flows, target_account, "income", income_amount
                    )

        projected_income = projected_income.quantize(Decimal("0.01"))
        income_taxes = (projected_income * tax_rate).quantize(Decimal("0.01"))
        projected_spending = _projected_spending_for_year(
            spending_baseline,
            year,
            effective_spending_inflation_rate,
        )
        if projected_spending != Decimal("0.00"):
            withdrawal_result.add(
                _withdraw_from_assets(
                    accounts,
                    accounts_by_id,
                    balances,
                    cash_flows,
                    projected_spending,
                    "spending",
                    effective_spending_account_id,
                    tax_rate,
                )
            )
        withdrawal_taxes = (withdrawal_result.taxable_amount * tax_rate).quantize(Decimal("0.01"))
        projected_taxes = (income_taxes + withdrawal_taxes).quantize(Decimal("0.01"))
        projected_liquidation_expenses = withdrawal_result.liquidation_expenses
        if income_taxes != Decimal("0.00"):
            tax_payment_result = _withdraw_from_assets(
                accounts,
                accounts_by_id,
                balances,
                cash_flows,
                income_taxes,
                "tax_payment",
                effective_tax_account_id,
                tax_rate,
            )
            projected_taxes = (
                projected_taxes + (tax_payment_result.taxable_amount * tax_rate)
            ).quantize(Decimal("0.01"))
            projected_liquidation_expenses = (
                projected_liquidation_expenses + tax_payment_result.liquidation_expenses
            ).quantize(Decimal("0.01"))
        net_cash_flow = (
            projected_income - projected_taxes - projected_spending - projected_liquidation_expenses
        ).quantize(
            Decimal("0.01")
        )

        account_points = [
            {
                "account_id": account.id,
                "name": account.name,
                "account_kind": account.account_kind,
                "category": account.category,
                "liquidity_class": account.liquidity_class,
                "projected_balance": balances[account.id],
            }
            for account in accounts
        ]
        assets_total = sum(
            (balances[account.id] for account in accounts if account.account_kind == AccountKind.asset),
            Decimal("0.00"),
        )
        liabilities_total = sum(
            (balances[account.id] for account in accounts if account.account_kind == AccountKind.liability),
            Decimal("0.00"),
        )
        points.append(
            {
                "year": year,
                "as_of_date": as_of_date,
                "net_worth": assets_total - liabilities_total,
                "assets_total": assets_total,
                "liabilities_total": liabilities_total,
                "projected_income": projected_income,
                "projected_taxes": projected_taxes,
                "projected_spending": projected_spending,
                "projected_liquidation_expenses": projected_liquidation_expenses,
                "net_cash_flow": net_cash_flow,
                "cash_flows": cash_flows,
                "accounts": account_points,
            }
        )

    return {
        "household_id": household_id,
        "start_year": start_year,
        "end_year": end_year,
        "points": points,
    }


def _latest_effective_tax_rate(db: Session, household_id: UUID) -> Decimal:
    tax_records = db.scalars(
        select(AnnualTaxRecord)
        .where(AnnualTaxRecord.household_id == household_id)
        .order_by(AnnualTaxRecord.tax_year.desc())
    ).all()
    for tax_record in tax_records:
        if tax_record.effective_tax_rate is not None:
            return tax_record.effective_tax_rate
    return Decimal("0.00")


def _projected_spending_for_year(
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


def _projected_income_for_year(income_sources: list[IncomeSource], year: int) -> Decimal:
    return sum(
        (_projected_income_source_for_year(source, year) for source in income_sources),
        Decimal("0.00"),
    )


def _projected_income_source_for_year(source: IncomeSource, year: int) -> Decimal:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    if source.start_date > year_end or (source.end_date is not None and source.end_date < year_start):
        return Decimal("0.00")

    annual_amount = _annualize_income(source.amount, source.frequency)
    growth_rate = source.growth_rate if source.growth_rate is not None else DEFAULT_INCOME_GROWTH_RATE
    years_elapsed = max(year - source.start_date.year, 0)
    return (annual_amount * ((Decimal("1") + growth_rate) ** years_elapsed)).quantize(Decimal("0.01"))


def _annualize_income(amount: Decimal, frequency: str) -> Decimal:
    multipliers = {
        IncomeFrequency.weekly: Decimal("52"),
        IncomeFrequency.biweekly: Decimal("26"),
        IncomeFrequency.semimonthly: Decimal("24"),
        IncomeFrequency.monthly: Decimal("12"),
        IncomeFrequency.quarterly: Decimal("4"),
        IncomeFrequency.annually: Decimal("1"),
    }
    return amount * multipliers.get(frequency, Decimal("1"))


def _validate_cash_flow_account(
    accounts_by_id: dict[UUID, Account], account_id: UUID | None, label: str
) -> None:
    if account_id is None:
        return
    account = accounts_by_id.get(account_id)
    if account is None or account.account_kind != AccountKind.asset:
        raise ValueError(f"{label} must be an active asset account in the household")


def _cash_flow_target_account(
    accounts: list[Account], accounts_by_id: dict[UUID, Account], account_id: UUID | None
) -> Account | None:
    if account_id is not None:
        return accounts_by_id[account_id]
    asset_accounts = [account for account in accounts if account.account_kind == AccountKind.asset]
    if not asset_accounts:
        return None
    return min(asset_accounts, key=_cash_flow_priority)


def _apply_account_cash_flow(
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    account: Account,
    cash_flow_type: str,
    amount: Decimal,
) -> None:
    amount = amount.quantize(Decimal("0.01"))
    balances[account.id] = (balances[account.id] + amount).quantize(Decimal("0.01"))
    cash_flows.append(
        {
            "account_id": account.id,
            "account_name": account.name,
            "cash_flow_type": cash_flow_type,
            "amount": amount,
        }
    )


def _apply_real_estate_sale(
    accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    sale: RealEstateSale,
    mortgage_profile: MortgageProfile | None,
    sold_mortgage_account_ids: set[UUID],
    tax_rate: Decimal,
) -> WithdrawalResult:
    property_account = accounts_by_id.get(sale.property_account_id)
    proceeds_account = accounts_by_id.get(sale.proceeds_account_id)
    if property_account is None or proceeds_account is None:
        raise ValueError("Property sale accounts must be active accounts in the household")

    property_balance = max(balances[property_account.id], Decimal("0.00"))
    if property_balance != Decimal("0.00"):
        _apply_account_cash_flow(
            balances, cash_flows, property_account, "property_sale_removal", -property_balance
        )

    mortgage_payoff = Decimal("0.00")
    if mortgage_profile is not None:
        mortgage_account = accounts_by_id.get(mortgage_profile.liability_account_id)
        if mortgage_account is not None:
            mortgage_payoff = max(balances[mortgage_account.id], Decimal("0.00"))
            if mortgage_payoff != Decimal("0.00"):
                _apply_account_cash_flow(
                    balances, cash_flows, mortgage_account, "mortgage_payoff", -mortgage_payoff
                )
            sold_mortgage_account_ids.add(mortgage_account.id)

    selling_expense_rate = (
        sale.selling_expense_rate
        if sale.selling_expense_rate is not None
        else _liquidation_expense_rate(property_account)
    )
    selling_expense = (sale.gross_sale_price * selling_expense_rate).quantize(Decimal("0.01"))
    if selling_expense != Decimal("0.00"):
        cash_flows.append(
            {
                "account_id": property_account.id,
                "account_name": property_account.name,
                "cash_flow_type": "property_sale_expense",
                "amount": -selling_expense,
            }
        )

    net_proceeds = (sale.gross_sale_price - mortgage_payoff - selling_expense).quantize(
        Decimal("0.01")
    )
    if net_proceeds >= Decimal("0.00"):
        if net_proceeds != Decimal("0.00"):
            _apply_account_cash_flow(
                balances, cash_flows, proceeds_account, "property_sale_proceeds", net_proceeds
            )
        return WithdrawalResult(liquidation_expenses=selling_expense)

    shortfall_result = _withdraw_from_assets(
        [account for account in accounts if account.id != property_account.id],
        accounts_by_id,
        balances,
        cash_flows,
        abs(net_proceeds),
        "property_sale_shortfall",
        None,
        tax_rate,
    )
    shortfall_result.liquidation_expenses = (
        shortfall_result.liquidation_expenses + selling_expense
    ).quantize(Decimal("0.01"))
    return shortfall_result


def _apply_projection_event(
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    event: AccountEvent,
    tax_rate: Decimal,
) -> WithdrawalResult:
    account = accounts_by_id.get(event.account_id)
    if account is None:
        return WithdrawalResult()

    amount = _projection_event_amount(event)
    if amount == Decimal("0.00"):
        return WithdrawalResult()

    if account.account_kind == AccountKind.asset and amount < Decimal("0.00"):
        return _withdraw_from_assets(
            list(accounts_by_id.values()),
            accounts_by_id,
            balances,
            cash_flows,
            abs(amount),
            event.event_type,
            event.account_id,
            tax_rate,
        )

    _apply_account_cash_flow(balances, cash_flows, account, event.event_type, amount)
    return WithdrawalResult()


def _projection_event_amount(event: AccountEvent) -> Decimal:
    if event.event_type in AccountEventOutflowTypes:
        return -abs(event.amount)
    if event.event_type in AccountEventInflowTypes:
        return abs(event.amount)
    return event.amount


def _withdraw_from_assets(
    accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    amount: Decimal,
    cash_flow_type: str,
    preferred_account_id: UUID | None,
    tax_rate: Decimal,
) -> WithdrawalResult:
    remaining_net = amount.quantize(Decimal("0.01"))
    result = WithdrawalResult()
    if remaining_net == Decimal("0.00"):
        return result

    asset_accounts = [account for account in accounts if account.account_kind == AccountKind.asset]
    if not asset_accounts:
        return result

    ordered_accounts = _withdrawal_order(asset_accounts, accounts_by_id, preferred_account_id)
    for account in ordered_accounts:
        available = max(balances[account.id], Decimal("0.00"))
        if available == Decimal("0.00"):
            continue

        taxes_apply = _withdrawal_has_tax_consequences(account)
        effective_tax_rate = tax_rate if taxes_apply else Decimal("0.00")
        liquidation_expense_rate = _liquidation_expense_rate(account)
        drag_rate = effective_tax_rate + liquidation_expense_rate
        if drag_rate >= Decimal("1.00"):
            continue

        gross_needed = (remaining_net / (Decimal("1.00") - drag_rate)).quantize(
            Decimal("0.01"), rounding=ROUND_UP
        )
        gross_deduction = min(available, gross_needed)
        if gross_deduction == Decimal("0.00"):
            continue

        tax_amount = (gross_deduction * effective_tax_rate).quantize(Decimal("0.01"))
        liquidation_expense = (gross_deduction * liquidation_expense_rate).quantize(
            Decimal("0.01")
        )
        net_amount = (gross_deduction - tax_amount - liquidation_expense).quantize(
            Decimal("0.01")
        )
        if net_amount == Decimal("0.00"):
            continue

        _apply_account_cash_flow(balances, cash_flows, account, cash_flow_type, -net_amount)
        if tax_amount != Decimal("0.00"):
            _apply_account_cash_flow(balances, cash_flows, account, "tax_payment", -tax_amount)
        if liquidation_expense != Decimal("0.00"):
            _apply_account_cash_flow(
                balances, cash_flows, account, "liquidation_expense", -liquidation_expense
            )

        result.net_amount = (result.net_amount + net_amount).quantize(Decimal("0.01"))
        if taxes_apply:
            result.taxable_amount = (result.taxable_amount + gross_deduction).quantize(
                Decimal("0.01")
            )
        result.liquidation_expenses = (
            result.liquidation_expenses + liquidation_expense
        ).quantize(Decimal("0.01"))
        remaining_net = (remaining_net - net_amount).quantize(Decimal("0.01"))
        # Rounding gross withdrawals up can satisfy the requested net amount by
        # a cent. Treat that as fully funded instead of running a second,
        # negative withdrawal that creates compensating micro cash flows.
        if remaining_net <= Decimal("0.00"):
            return result

    return result


def _withdrawal_has_tax_consequences(account: Account) -> bool:
    return account.category not in {"cash", "checking", "savings"}


def _liquidation_expense_rate(account: Account) -> Decimal:
    if account.liquidation_expense_rate is not None:
        return account.liquidation_expense_rate
    return DEFAULT_LIQUIDATION_EXPENSE_RATES.get(account.category, Decimal("0.000000"))


def _funding_priority(account: Account) -> tuple[int, str] | None:
    account_name = account.name.casefold()
    if account_name in DEFAULT_FUNDING_ACCOUNT_NAMES:
        return (0, account_name)
    if (
        account.category in {"taxable_investment", "brokerage"}
        and account.liquidity_class in LIQUIDITY_CLASSES
    ):
        return (1, account_name)
    if account.category == "retirement" and "roth" in account_name:
        return (2, account_name)
    if account.category == "retirement" and account.liquidity_class in LIQUIDITY_CLASSES:
        return (3, account_name)
    if account.category in BANK_CATEGORIES:
        return (4, account_name)
    if account.category != "real_estate" and account.liquidity_class in LIQUIDITY_CLASSES:
        return (5, account_name)
    return None


def _withdrawal_order(
    asset_accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    preferred_account_id: UUID | None,
) -> list[Account]:
    ordered_accounts = sorted(
        (account for account in asset_accounts if _funding_priority(account) is not None),
        key=_funding_priority,
    )
    if preferred_account_id is None:
        return ordered_accounts
    preferred_account = accounts_by_id[preferred_account_id]
    return [preferred_account] + [
        account for account in ordered_accounts if account.id != preferred_account_id
    ]


def _cash_flow_priority(account: Account) -> tuple[int, str]:
    return (CASH_FLOW_CATEGORY_PRIORITY.get(account.category, 99), account.name)


def _latest_balance_on_or_before(db: Session, account_id: UUID, as_of_date: date) -> Decimal | None:
    snapshot = db.scalars(
        select(BalanceSnapshot)
        .where(BalanceSnapshot.account_id == account_id, BalanceSnapshot.as_of_date <= as_of_date)
        .order_by(BalanceSnapshot.as_of_date.desc(), BalanceSnapshot.created_at.desc())
        .limit(1)
    ).first()
    return snapshot.balance if snapshot else None


def _yield_for_account(
    account: Account,
    property_profile: RealEstateProperty | None,
) -> Decimal:
    if account.expected_annual_yield is not None:
        return account.expected_annual_yield
    if property_profile is not None and property_profile.expected_appreciation_rate is not None:
        return property_profile.expected_appreciation_rate
    if account.account_kind == AccountKind.liability:
        return Decimal("0.000000")
    return DEFAULT_CATEGORY_YIELDS.get(account.category, Decimal("0.030000"))
