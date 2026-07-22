from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, selectinload

from app.core.security import require_authenticated_user
from app.db.models import HouseholdMembership, User
from app.db.session import get_db
from app.schemas.household import HouseholdRead
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


def _normalized_email(email: str | None) -> str | None:
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Display name is required")

    user = User(display_name=display_name, email=_normalized_email(payload.email))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists",
        ) from exc
    db.refresh(user)
    return user


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> list[User]:
    current_households = select(HouseholdMembership.household_id).where(
        HouseholdMembership.user_id == current_user.id
    )
    shared_users = select(HouseholdMembership.user_id).where(
        HouseholdMembership.household_id.in_(current_households)
    )
    return list(
        db.scalars(
            select(User)
            .where(or_(User.id == current_user.id, User.id.in_(shared_users)))
            .order_by(User.created_at, User.display_name)
        ).all()
    )


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id != current_user.id:
        actor_membership = aliased(HouseholdMembership)
        target_membership = aliased(HouseholdMembership)
        shared_household = db.scalar(
            select(target_membership.id)
            .join(
                actor_membership,
                actor_membership.household_id == target_membership.household_id,
            )
            .where(
                actor_membership.user_id == current_user.id,
                target_membership.user_id == user_id,
            )
            .limit(1)
        )
        if shared_household is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/{user_id}/households", response_model=list[HouseholdRead])
def list_user_households(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> list:
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot list another user's households",
        )

    memberships = db.scalars(
        select(HouseholdMembership)
        .options(selectinload(HouseholdMembership.household))
        .where(HouseholdMembership.user_id == user_id)
        .order_by(HouseholdMembership.created_at)
    ).all()
    return [membership.household for membership in memberships]

