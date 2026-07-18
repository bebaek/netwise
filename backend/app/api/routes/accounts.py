from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountEvent,
    BalanceSnapshot,
    Household,
    RetirementTaxTreatment,
)
from app.db.session import get_db
from app.schemas.account import (
    AccountCreate,
    AccountEventCreate,
    AccountEventRead,
    AccountEventUpdate,
    AccountRead,
    AccountUpdate,
    BalanceSnapshotCreate,
    BalanceSnapshotRead,
    BalanceSnapshotUpdate,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.patch(
    "/{account_id}/snapshots/{snapshot_id}",
    response_model=BalanceSnapshotRead,
)
def update_snapshot(
    account_id: UUID,
    snapshot_id: UUID,
    payload: BalanceSnapshotUpdate,
    db: Session = Depends(get_db),
) -> BalanceSnapshot:
    snapshot = db.get(BalanceSnapshot, snapshot_id)
    if snapshot is None or snapshot.account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(snapshot, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A snapshot already exists for this account and date",
        ) from exc
    db.refresh(snapshot)
    return snapshot


@router.delete("/{account_id}/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(
    account_id: UUID,
    snapshot_id: UUID,
    db: Session = Depends(get_db),
) -> Response:
    snapshot = db.get(BalanceSnapshot, snapshot_id)
    if snapshot is None or snapshot.account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")

    db.delete(snapshot)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    values = payload.model_dump()
    if values["category"] != "retirement":
        values["retirement_tax_treatment"] = None
    elif values["retirement_tax_treatment"] is None:
        values["retirement_tax_treatment"] = RetirementTaxTreatment.traditional
    account = Account(**values)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[AccountRead])
def list_accounts(household_id: UUID, db: Session = Depends(get_db)) -> list[Account]:
    return list(
        db.scalars(
            select(Account).where(Account.household_id == household_id).order_by(Account.name)
        ).all()
    )


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: UUID, db: Session = Depends(get_db)) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: UUID,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    if account.category != "retirement":
        account.retirement_tax_treatment = None
    elif account.retirement_tax_treatment is None:
        account.retirement_tax_treatment = RetirementTaxTreatment.traditional
    db.commit()
    db.refresh(account)
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


@router.post(
    "/{account_id}/events",
    response_model=AccountEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    account_id: UUID,
    payload: AccountEventCreate,
    db: Session = Depends(get_db),
) -> AccountEvent:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    event = AccountEvent(
        household_id=account.household_id,
        account_id=account.id,
        **payload.model_dump(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch(
    "/{account_id}/events/{event_id}",
    response_model=AccountEventRead,
)
def update_event(
    account_id: UUID,
    event_id: UUID,
    payload: AccountEventUpdate,
    db: Session = Depends(get_db),
) -> AccountEvent:
    account_event = db.get(AccountEvent, event_id)
    if account_event is None or account_event.account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    updates = payload.model_dump(exclude_unset=True)
    new_account_id = updates.pop("account_id", None)
    if new_account_id is not None:
        new_account = db.get(Account, new_account_id)
        if new_account is None or new_account.household_id != account_event.household_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid account")
        account_event.account_id = new_account.id

    for key, value in updates.items():
        setattr(account_event, key, value)

    db.commit()
    db.refresh(account_event)
    return account_event


@router.delete("/{account_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(account_id: UUID, event_id: UUID, db: Session = Depends(get_db)) -> Response:
    account_event = db.get(AccountEvent, event_id)
    if account_event is None or account_event.account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    db.delete(account_event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{account_id}/events", response_model=list[AccountEventRead])
def list_events(account_id: UUID, db: Session = Depends(get_db)) -> list[AccountEvent]:
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return list(
        db.scalars(
            select(AccountEvent)
            .where(AccountEvent.account_id == account_id)
            .order_by(AccountEvent.event_date.desc(), AccountEvent.created_at.desc())
        ).all()
    )
