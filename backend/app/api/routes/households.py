from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Account, BalanceSnapshot, Household, HouseholdMembership, MembershipRole, User
from app.db.session import get_db
from app.schemas.account import (
    BalanceSnapshotBatchCreate,
    BalanceSnapshotBatchRead,
    HouseholdBalanceSnapshotRead,
)
from app.schemas.household import HouseholdCreate, HouseholdRead
from app.schemas.user import HouseholdMembershipCreate, HouseholdMembershipRead

router = APIRouter(prefix="/households", tags=["households"])

_ALLOWED_ROLES = {role.value for role in MembershipRole}


def validate_membership_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {', '.join(sorted(_ALLOWED_ROLES))}",
        )
    return normalized


@router.post("", response_model=HouseholdRead, status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> Household:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Household name is required")

    if payload.owner_user_id is not None and db.get(User, payload.owner_user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner user not found")

    household = Household(name=name)
    db.add(household)
    db.flush()
    if payload.owner_user_id is not None:
        db.add(
            HouseholdMembership(
                household_id=household.id,
                user_id=payload.owner_user_id,
                role="owner",
            )
        )
    db.commit()
    db.refresh(household)
    return household


@router.get("", response_model=list[HouseholdRead])
def list_households(user_id: UUID | None = None, db: Session = Depends(get_db)) -> list[Household]:
    if user_id is None:
        return list(db.scalars(select(Household).order_by(Household.created_at)).all())

    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    statement = (
        select(Household)
        .join(HouseholdMembership, HouseholdMembership.household_id == Household.id)
        .where(HouseholdMembership.user_id == user_id)
        .order_by(Household.created_at)
    )
    return list(db.scalars(statement).all())


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


@router.get("/{household_id}/members", response_model=list[HouseholdMembershipRead])
def list_household_members(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[HouseholdMembership]:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    return list(
        db.scalars(
            select(HouseholdMembership)
            .options(selectinload(HouseholdMembership.user))
            .where(HouseholdMembership.household_id == household_id)
            .order_by(HouseholdMembership.created_at)
        ).all()
    )


@router.post(
    "/{household_id}/members",
    response_model=HouseholdMembershipRead,
    status_code=status.HTTP_201_CREATED,
)
def add_household_member(
    household_id: UUID,
    payload: HouseholdMembershipCreate,
    db: Session = Depends(get_db),
) -> HouseholdMembership:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = db.scalars(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == payload.user_id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this household",
        )

    membership = HouseholdMembership(
        household_id=household_id,
        user_id=payload.user_id,
        role=validate_membership_role(payload.role),
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.delete("/{household_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_household_member(
    household_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    membership = db.scalars(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    db.delete(membership)
    db.commit()


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
