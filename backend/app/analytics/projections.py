from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.expense_estimation import ExpenseEstimateError, estimate_annual_living_expense
from app.analytics.mortgage import estimate_mortgage_balance
from app.db.models import (
    Account,
    AccountEvent,
    AccountKind,
    AnnualTaxRecord,
    BalanceSnapshot,
    IncomeFrequency,
    IncomeSource,
    MortgageProfile,
    ProjectionBehavior,
    RealEstateProperty,
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


CASH_FLOW_CATEGORY_PRIORITY = {
    "cash": 0,
    "checking": 0,
    "savings": 1,
    "taxable_investment": 2,
    "brokerage": 2,
    "retirement": 3,
    "real_estate": 4,
}


def calculate_net_worth_projection(
    db: Session,
    household_id: UUID,
    *,
    start_year: int,
    end_year: int,
    annual_spending: Decimal | None = None,
    spending_inflation_rate: Decimal = DEFAULT_SPENDING_INFLATION_RATE,
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
    spending_baseline = (
        (start_year, annual_spending.quantize(Decimal("0.01")))
        if annual_spending is not None
        else _latest_living_expense_estimate(db, household_id)
    )
    tax_rate = _latest_effective_tax_rate(db, household_id)

    points = []
    for year in range(start_year, end_year + 1):
        as_of_date = date(year, 12, 31)
        year_start = date(year, 1, 1)

        for account in accounts:
            if account.id in mortgage_profiles:
                balances[account.id] = estimate_mortgage_balance(
                    mortgage_profiles[account.id], as_of_date
                )
                continue

            annual_yield = _yield_for_account(account, property_profiles.get(account.id))
            balances[account.id] = (balances[account.id] * (Decimal("1") + annual_yield)).quantize(
                Decimal("0.01")
            )

        for event in projection_events:
            if year_start <= event.event_date <= as_of_date:
                balances[event.account_id] = (balances.get(event.account_id, Decimal("0.00")) + event.amount).quantize(
                    Decimal("0.01")
                )

        projected_income = _projected_income_for_year(income_sources, year)
        projected_taxes = (projected_income * tax_rate).quantize(Decimal("0.01"))
        projected_spending = _projected_spending_for_year(
            spending_baseline,
            year,
            spending_inflation_rate,
        )
        net_cash_flow = (projected_income - projected_taxes - projected_spending).quantize(Decimal("0.01"))
        _apply_cash_flow_to_assets(accounts, balances, net_cash_flow)

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
                "net_cash_flow": net_cash_flow,
                "accounts": account_points,
            }
        )

    return {
        "household_id": household_id,
        "start_year": start_year,
        "end_year": end_year,
        "points": points,
    }


def _latest_living_expense_estimate(db: Session, household_id: UUID) -> tuple[int, Decimal] | None:
    tax_years = db.scalars(
        select(AnnualTaxRecord.tax_year)
        .where(AnnualTaxRecord.household_id == household_id)
        .order_by(AnnualTaxRecord.tax_year.desc())
    ).all()
    for tax_year in tax_years:
        try:
            estimate = estimate_annual_living_expense(db, household_id, tax_year)
        except ExpenseEstimateError:
            continue
        return tax_year, estimate["estimated_living_expense"].quantize(Decimal("0.01"))
    return None


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
    return sum((_projected_income_source_for_year(source, year) for source in income_sources), Decimal("0.00"))


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


def _apply_cash_flow_to_assets(
    accounts: list[Account],
    balances: dict[UUID, Decimal],
    net_cash_flow: Decimal,
) -> None:
    if net_cash_flow == Decimal("0.00"):
        return

    asset_accounts = [account for account in accounts if account.account_kind == AccountKind.asset]
    if not asset_accounts:
        return

    if net_cash_flow > Decimal("0.00"):
        target = min(asset_accounts, key=_cash_flow_priority)
        balances[target.id] = (balances[target.id] + net_cash_flow).quantize(Decimal("0.01"))
        return

    remaining_spend = -net_cash_flow
    for account in sorted(asset_accounts, key=_cash_flow_priority):
        available = max(balances[account.id], Decimal("0.00"))
        deduction = min(available, remaining_spend)
        balances[account.id] = (balances[account.id] - deduction).quantize(Decimal("0.01"))
        remaining_spend -= deduction
        if remaining_spend == Decimal("0.00"):
            return

    target = min(asset_accounts, key=_cash_flow_priority)
    balances[target.id] = (balances[target.id] - remaining_spend).quantize(Decimal("0.01"))


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
