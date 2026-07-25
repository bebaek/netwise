from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.projection_contracts import (
    ProjectionAccount,
    ProjectionEvent,
    ProjectionIncomeSource,
    ProjectionSettingsInput,
    ProjectionSpendingItem,
    ProjectionTransferInput,
)
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
    projection_events: tuple[ProjectionEvent, ...]
    income_sources: tuple[ProjectionIncomeSource, ...]
    projection_transfers: tuple[ProjectionTransferInput, ...]
    spending_items: tuple[ProjectionSpendingItem, ...]
    projection_settings: ProjectionSettingsInput | None
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
    projection_event_records = list(
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
    income_source_records = list(
        db.scalars(select(IncomeSource).where(IncomeSource.household_id == household_id)).all()
    )
    projection_transfer_records = list(
        db.scalars(
            select(ProjectionTransfer)
            .where(ProjectionTransfer.household_id == household_id)
            .order_by(ProjectionTransfer.name, ProjectionTransfer.created_at)
        ).all()
    )
    spending_item_records = list(
        db.scalars(
            select(SpendingItem)
            .where(SpendingItem.household_id == household_id)
            .order_by(SpendingItem.category, SpendingItem.name, SpendingItem.created_at)
        ).all()
    )
    projection_settings_record = db.scalars(
        select(ProjectionSettings).where(ProjectionSettings.household_id == household_id)
    ).first()
    tax_rate = _latest_effective_tax_rate(db, household_id)
    cost_bases, cost_basis_estimates = _resolve_cost_bases(db, account_records, start_date)
    accounts = tuple(_to_projection_account(account) for account in account_records)
    projection_events = tuple(_to_projection_event(event) for event in projection_event_records)
    income_sources = tuple(_to_projection_income(source) for source in income_source_records)
    projection_transfers = tuple(
        _to_projection_transfer(transfer) for transfer in projection_transfer_records
    )
    spending_items = tuple(_to_projection_spending_item(item) for item in spending_item_records)
    projection_settings = (
        _to_projection_settings(projection_settings_record)
        if projection_settings_record is not None
        else None
    )
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


def _to_projection_event(event: AccountEvent) -> ProjectionEvent:
    return ProjectionEvent(
        account_id=event.account_id,
        event_date=event.event_date,
        amount=event.amount,
        event_type=event.event_type,
    )


def _to_projection_income(source: IncomeSource) -> ProjectionIncomeSource:
    return ProjectionIncomeSource(
        amount=source.amount,
        frequency=source.frequency,
        start_date=source.start_date,
        end_date=source.end_date,
        growth_rate=source.growth_rate,
        deposit_account_id=source.deposit_account_id,
    )


def _to_projection_transfer(transfer: ProjectionTransfer) -> ProjectionTransferInput:
    return ProjectionTransferInput(
        from_account_id=transfer.from_account_id,
        to_account_id=transfer.to_account_id,
        annual_amount=transfer.annual_amount,
        start_date=transfer.start_date,
        end_date=transfer.end_date,
        growth_rate=transfer.growth_rate,
    )


def _to_projection_spending_item(item: SpendingItem) -> ProjectionSpendingItem:
    return ProjectionSpendingItem(
        name=item.name,
        category=item.category,
        annual_amount=item.annual_amount,
        retirement_annual_amount=item.retirement_annual_amount,
        growth_rate=item.growth_rate,
    )


def _to_projection_settings(settings: ProjectionSettings) -> ProjectionSettingsInput:
    return ProjectionSettingsInput(
        annual_spending=settings.annual_spending,
        spending_mode=settings.spending_mode,
        spending_inflation_rate=settings.spending_inflation_rate,
        retirement_date=settings.retirement_date,
        retirement_annual_spending=settings.retirement_annual_spending,
        spending_account_id=settings.spending_account_id,
        tax_account_id=settings.tax_account_id,
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
