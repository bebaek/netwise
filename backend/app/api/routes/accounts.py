from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, BalanceSnapshot, Household
from app.db.session import get_db
from app.schemas.account import AccountCreate, AccountRead, BalanceSnapshotCreate, BalanceSnapshotRead

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    account = Account(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[AccountRead])
def list_accounts(household_id: UUID, db: Session = Depends(get_db)) -> list[Account]:
    return list(
        db.scalars(
            select(Account)
            .where(Account.household_id == household_id)
            .order_by(Account.name)
        ).all()
    )


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: UUID, db: Session = Depends(get_db)) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.post(
    "/{account_id}/snapshots",
    response_model=BalanceSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    account_id: UUID,
    payload: BalanceSnapshotCreate,
    db: Session = Depends(get_db),
) -> BalanceSnapshot:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    snapshot = BalanceSnapshot(
        household_id=account.household_id,
        account_id=account.id,
        **payload.model_dump(),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/{account_id}/snapshots", response_model=list[BalanceSnapshotRead])
def list_snapshots(account_id: UUID, db: Session = Depends(get_db)) -> list[BalanceSnapshot]:
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return list(
        db.scalars(
            select(BalanceSnapshot)
            .where(BalanceSnapshot.account_id == account_id)
            .order_by(BalanceSnapshot.as_of_date.desc())
        ).all()
    )
