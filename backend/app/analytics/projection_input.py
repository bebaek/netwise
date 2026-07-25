from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.projection_contracts import ProjectionAccount
from app.db.models import (
    Account,
    AccountEvent,
    AnnualTaxRecord,
    BalanceSnapshot,
    IncomeSource,
    MortgageProfile,
    ProjectionBehavior,
    ProjectionSettings,
    ProjectionTransfer,
    RealEstateLiquidationStrategy,
    RealEstateProperty,
    RealEstateSale,
    SpendingItem,
)

TAXABLE_INVESTMENT_CATEGORIES = {"taxable_investment", "brokerage"}


@dataclass(frozen=True)
class ProjectionInput:
    """Database-backed input snapshot consumed by the deterministic projection.

    The container is immutable so candidate optimization runs can safely reuse
    the same resolved input. Its values remain ORM records during this first
    boundary extraction; converting them to plain domain records is a separate
    follow-up step.
    """

    household_id: UUID
    accounts: tuple[ProjectionAccount, ...]
    initial_balances: dict[UUID, Decimal]
    mortgage_profiles: dict[UUID, MortgageProfile]
    property_profiles: dict[UUID, RealEstateProperty]
    real_estate_sales: list[RealEstateSale]
    automatic_sale_strategies: list[RealEstateLiquidationStrategy]
    projection_events: list[AccountEvent]
    income_sources: list[IncomeSource]
    projection_transfers: list[ProjectionTransfer]
    spending_items: list[SpendingItem]
    projection_settings: ProjectionSettings | None
    tax_rate: Decimal
    cost_bases: dict[UUID, Decimal]
    cost_basis_estimates: dict[UUID, tuple[Decimal, date]]


def load_projection_input(
    db: Session,
    household_id: UUID,
    *,
    start_date: date,
    end_date: date,
) -> ProjectionInput:
    """Resolve all persisted records needed for a deterministic projection."""
    account_records = list(
        db.scalars(
            select(Account)
            .where(Account.household_id == household_id, Account.is_active.is_(True))
            .order_by(Account.name)
        ).all()
    )
    initial_balances = {
        account.id: _latest_balance_on_or_before(db, account.id, start_date) or Decimal("0.00")
        for account in account_records
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
            .where(RealEstateSale.household_id == household_id)
            .order_by(RealEstateSale.sale_date)
        ).all()
    )
    automatic_sale_strategies = list(
        db.scalars(
            select(RealEstateLiquidationStrategy)
            .where(RealEstateLiquidationStrategy.household_id == household_id)
            .order_by(
                RealEstateLiquidationStrategy.priority,
                RealEstateLiquidationStrategy.created_at,
            )
        ).all()
    )
    projection_events = list(
        db.scalars(
            select(AccountEvent)
            .where(
                AccountEvent.household_id == household_id,
                AccountEvent.projection_behavior != ProjectionBehavior.historical_only,
                AccountEvent.event_date >= start_date,
                AccountEvent.event_date <= end_date,
            )
            .order_by(AccountEvent.event_date)
        ).all()
    )
    income_sources = list(
        db.scalars(select(IncomeSource).where(IncomeSource.household_id == household_id)).all()
    )
    projection_transfers = list(
        db.scalars(
            select(ProjectionTransfer)
            .where(ProjectionTransfer.household_id == household_id)
            .order_by(ProjectionTransfer.name, ProjectionTransfer.created_at)
        ).all()
    )
    spending_items = list(
        db.scalars(
            select(SpendingItem)
            .where(SpendingItem.household_id == household_id)
            .order_by(SpendingItem.category, SpendingItem.name, SpendingItem.created_at)
        ).all()
    )
    projection_settings = db.scalars(
        select(ProjectionSettings).where(ProjectionSettings.household_id == household_id)
    ).first()
    tax_rate = _latest_effective_tax_rate(db, household_id)
    cost_bases, cost_basis_estimates = _resolve_cost_bases(db, account_records, start_date)
    accounts = tuple(_to_projection_account(account) for account in account_records)
    return ProjectionInput(
        household_id=household_id,
        accounts=accounts,
        initial_balances=initial_balances,
        mortgage_profiles=mortgage_profiles,
        property_profiles=property_profiles,
        real_estate_sales=real_estate_sales,
        automatic_sale_strategies=automatic_sale_strategies,
        projection_events=projection_events,
        income_sources=income_sources,
        projection_transfers=projection_transfers,
        spending_items=spending_items,
        projection_settings=projection_settings,
        tax_rate=tax_rate,
        cost_bases=cost_bases,
        cost_basis_estimates=cost_basis_estimates,
    )


def _to_projection_account(account: Account) -> ProjectionAccount:
    return ProjectionAccount(
        id=account.id,
        name=account.name,
        account_kind=account.account_kind,
        category=account.category,
        liquidity_class=account.liquidity_class,
        retirement_tax_treatment=account.retirement_tax_treatment,
        expected_annual_yield=account.expected_annual_yield,
        liquidation_expense_rate=account.liquidation_expense_rate,
    )


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


def _latest_balance_on_or_before(db: Session, account_id: UUID, as_of_date: date) -> Decimal | None:
    snapshot = db.scalars(
        select(BalanceSnapshot)
        .where(BalanceSnapshot.account_id == account_id, BalanceSnapshot.as_of_date <= as_of_date)
        .order_by(BalanceSnapshot.as_of_date.desc(), BalanceSnapshot.created_at.desc())
        .limit(1)
    ).first()
    return snapshot.balance if snapshot else None


def _earliest_snapshot(db: Session, account_id: UUID) -> BalanceSnapshot | None:
    return db.scalars(
        select(BalanceSnapshot)
        .where(BalanceSnapshot.account_id == account_id)
        .order_by(BalanceSnapshot.as_of_date, BalanceSnapshot.created_at)
        .limit(1)
    ).first()


def _resolve_cost_bases(
    db: Session, accounts: list[Account], start_date: date
) -> tuple[dict[UUID, Decimal], dict[UUID, tuple[Decimal, date]]]:
    """Resolve explicit or estimated starting bases for taxable accounts."""
    cost_bases: dict[UUID, Decimal] = {}
    estimates: dict[UUID, tuple[Decimal, date]] = {}
    for account in accounts:
        if account.category not in TAXABLE_INVESTMENT_CATEGORIES:
            continue
        if account.cost_basis is not None:
            cost_bases[account.id] = account.cost_basis
            continue
        earliest = _earliest_snapshot(db, account.id)
        if earliest is not None:
            cost_bases[account.id] = earliest.balance
            estimates[account.id] = (earliest.balance, earliest.as_of_date)
            continue
        latest = _latest_balance_on_or_before(db, account.id, start_date)
        cost_bases[account.id] = latest if latest is not None else Decimal("0.00")
    return cost_bases, estimates
