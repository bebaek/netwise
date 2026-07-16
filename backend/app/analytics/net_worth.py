from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, AccountKind, BalanceSnapshot


def latest_account_balances(db: Session, household_id: UUID) -> list[dict]:
    accounts = db.scalars(
        select(Account)
        .where(Account.household_id == household_id, Account.is_active.is_(True))
        .order_by(Account.name)
    ).all()

    rows = []
    for account in accounts:
        snapshot = db.scalars(
            select(BalanceSnapshot)
            .where(BalanceSnapshot.account_id == account.id)
            .order_by(BalanceSnapshot.as_of_date.desc(), BalanceSnapshot.created_at.desc())
            .limit(1)
        ).first()
        balance = snapshot.balance if snapshot else None
        signed_balance = signed_account_balance(account.account_kind, balance)
        rows.append(
            {
                "account_id": account.id,
                "name": account.name,
                "account_kind": account.account_kind,
                "category": account.category,
                "liquidity_class": account.liquidity_class,
                "balance": balance,
                "signed_balance": signed_balance,
            }
        )
    return rows


def signed_account_balance(account_kind: str, balance: Decimal | None) -> Decimal:
    if balance is None:
        return Decimal("0.00")
    if account_kind == AccountKind.liability:
        return -balance
    return balance


def calculate_net_worth(db: Session, household_id: UUID) -> dict:
    accounts = latest_account_balances(db, household_id)
    assets_total = sum(
        (row["balance"] or Decimal("0.00"))
        for row in accounts
        if row["account_kind"] == AccountKind.asset
    )
    liabilities_total = sum(
        (row["balance"] or Decimal("0.00"))
        for row in accounts
        if row["account_kind"] == AccountKind.liability
    )
    return {
        "household_id": household_id,
        "net_worth": assets_total - liabilities_total,
        "assets_total": assets_total,
        "liabilities_total": liabilities_total,
        "accounts": accounts,
    }


def calculate_net_worth_history(db: Session, household_id: UUID) -> dict:
    accounts = db.scalars(
        select(Account)
        .where(Account.household_id == household_id, Account.is_active.is_(True))
        .order_by(Account.name)
    ).all()
    if not accounts:
        return {"household_id": household_id, "points": []}

    snapshot_dates = list(
        db.scalars(
            select(BalanceSnapshot.as_of_date)
            .where(BalanceSnapshot.household_id == household_id)
            .distinct()
            .order_by(BalanceSnapshot.as_of_date)
        ).all()
    )

    points = []
    for as_of_date in snapshot_dates:
        assets_total = Decimal("0.00")
        liabilities_total = Decimal("0.00")
        for account in accounts:
            balance = _latest_balance_on_or_before(db, account.id, as_of_date)
            if balance is None:
                continue
            if account.account_kind == AccountKind.liability:
                liabilities_total += balance
            else:
                assets_total += balance
        points.append(
            {
                "as_of_date": as_of_date,
                "net_worth": assets_total - liabilities_total,
                "assets_total": assets_total,
                "liabilities_total": liabilities_total,
            }
        )

    return {"household_id": household_id, "points": points}


def _latest_balance_on_or_before(
    db: Session,
    account_id: UUID,
    as_of_date: date,
) -> Decimal | None:
    snapshot = db.scalars(
        select(BalanceSnapshot)
        .where(
            BalanceSnapshot.account_id == account_id,
            BalanceSnapshot.as_of_date <= as_of_date,
        )
        .order_by(BalanceSnapshot.as_of_date.desc(), BalanceSnapshot.created_at.desc())
        .limit(1)
    ).first()
    return snapshot.balance if snapshot else None
