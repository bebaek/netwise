from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, BalanceSnapshot, Household
from app.db.session import get_db
from app.schemas.account import (
    BalanceSnapshotBatchCreate,
    BalanceSnapshotBatchRead,
    HouseholdBalanceSnapshotRead,
)
from app.schemas.household import HouseholdCreate, HouseholdRead

router = APIRouter(prefix="/households", tags=["households"])


@router.post("", response_model=HouseholdRead, status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> Household:
    household = Household(name=payload.name)
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


@router.get("", response_model=list[HouseholdRead])
def list_households(db: Session = Depends(get_db)) -> list[Household]:
    return list(db.scalars(select(Household).order_by(Household.created_at)).all())


@router.get("/{household_id}/snapshots", response_model=list[HouseholdBalanceSnapshotRead])
def list_household_snapshots(
    household_id: UUID,
    account_id: UUID | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    statement = (
        select(BalanceSnapshot, Account)
        .join(Account, BalanceSnapshot.account_id == Account.id)
        .where(BalanceSnapshot.household_id == household_id)
        .order_by(BalanceSnapshot.as_of_date.desc(), Account.name, BalanceSnapshot.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if account_id is not None:
        statement = statement.where(BalanceSnapshot.account_id == account_id)

    rows = db.execute(statement).all()
    return [
        {
            "id": snapshot.id,
            "household_id": snapshot.household_id,
            "account_id": snapshot.account_id,
            "account_name": account.name,
            "account_kind": account.account_kind,
            "account_category": account.category,
            "as_of_date": snapshot.as_of_date,
            "balance": snapshot.balance,
            "currency": snapshot.currency,
            "source": snapshot.source,
            "confidence_level": snapshot.confidence_level,
            "created_at": snapshot.created_at,
        }
        for snapshot, account in rows
    ]


@router.get("/{household_id}", response_model=HouseholdRead)
def get_household(household_id: UUID, db: Session = Depends(get_db)) -> Household:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    return household


@router.post(
    "/{household_id}/snapshot-batch",
    response_model=BalanceSnapshotBatchRead,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot_batch(
    household_id: UUID,
    payload: BalanceSnapshotBatchCreate,
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    account_ids = [item.account_id for item in payload.snapshots]
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
            select(Account).where(
                Account.household_id == household_id,
                Account.id.in_(account_ids),
            )
        ).all()
    }
    missing_account_ids = [str(account_id) for account_id in account_ids if account_id not in accounts]
    if missing_account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Accounts do not belong to household: {', '.join(missing_account_ids)}",
        )

    created_count = 0
    updated_count = 0
    saved_snapshots: list[BalanceSnapshot] = []
    for item in payload.snapshots:
        snapshot = db.scalars(
            select(BalanceSnapshot)
            .where(
                BalanceSnapshot.account_id == item.account_id,
                BalanceSnapshot.as_of_date == payload.as_of_date,
            )
            .limit(1)
        ).first()
        if snapshot is None:
            snapshot = BalanceSnapshot(
                household_id=household_id,
                account_id=item.account_id,
                as_of_date=payload.as_of_date,
                balance=item.balance,
                currency=payload.currency,
                source=payload.source,
                confidence_level=payload.confidence_level,
            )
            db.add(snapshot)
            created_count += 1
        else:
            snapshot.balance = item.balance
            snapshot.currency = payload.currency
            snapshot.source = payload.source
            snapshot.confidence_level = payload.confidence_level
            updated_count += 1
        saved_snapshots.append(snapshot)

    db.commit()
    for snapshot in saved_snapshots:
        db.refresh(snapshot)

    return {
        "household_id": household_id,
        "as_of_date": payload.as_of_date,
        "created_count": created_count,
        "updated_count": updated_count,
        "snapshots": saved_snapshots,
    }
