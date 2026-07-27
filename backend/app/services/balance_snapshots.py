from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, BalanceSnapshot, Household


@dataclass(frozen=True, slots=True)
class BalanceSnapshotValue:
    account_id: UUID
    balance: Decimal


def save_snapshot_batch(
    db: Session,
    household_id: UUID,
    *,
    as_of_date: date,
    currency: str,
    source: str,
    confidence_level: str | None,
    snapshots: list[BalanceSnapshotValue],
) -> dict[str, object]:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    account_ids = [item.account_id for item in snapshots]
    duplicate_account_ids = sorted(
        {str(account_id) for account_id in account_ids if account_ids.count(account_id) > 1}
    )
    if duplicate_account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate accounts in snapshot batch: {', '.join(duplicate_account_ids)}",
        )

    accounts = {
        account.id: account
        for account in db.scalars(
            select(Account)
            .where(
                Account.household_id == household_id,
                Account.id.in_(account_ids),
            )
            .with_for_update()
        ).all()
    }
    missing_account_ids = [
        str(account_id) for account_id in account_ids if account_id not in accounts
    ]
    if missing_account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Accounts do not belong to household: {', '.join(missing_account_ids)}",
        )

    created_count = 0
    updated_count = 0
    saved_snapshots: list[BalanceSnapshot] = []
    for item in snapshots:
        snapshot = db.scalars(
            select(BalanceSnapshot)
            .where(
                BalanceSnapshot.account_id == item.account_id,
                BalanceSnapshot.as_of_date == as_of_date,
            )
            .with_for_update()
            .limit(1)
        ).first()
        if snapshot is None:
            snapshot = BalanceSnapshot(
                household_id=household_id,
                account_id=item.account_id,
                as_of_date=as_of_date,
                balance=item.balance,
                currency=currency,
                source=source,
                confidence_level=confidence_level,
            )
            db.add(snapshot)
            created_count += 1
        else:
            snapshot.balance = item.balance
            snapshot.currency = currency
            snapshot.source = source
            snapshot.confidence_level = confidence_level
            updated_count += 1
        saved_snapshots.append(snapshot)

    db.commit()
    for snapshot in saved_snapshots:
        db.refresh(snapshot)

    return {
        "household_id": household_id,
        "as_of_date": as_of_date,
        "created_count": created_count,
        "updated_count": updated_count,
        "snapshots": saved_snapshots,
    }
