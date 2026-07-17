from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.mortgage import estimate_mortgage_balance
from app.db.models import (
    Account,
    AccountEvent,
    AccountKind,
    BalanceSnapshot,
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


def calculate_net_worth_projection(
    db: Session,
    household_id: UUID,
    *,
    start_year: int,
    end_year: int,
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
                "accounts": account_points,
            }
        )

    return {
        "household_id": household_id,
        "start_year": start_year,
        "end_year": end_year,
        "points": points,
    }


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
