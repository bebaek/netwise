from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

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
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at, User.display_name)).all())


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/{user_id}/households", response_model=list[HouseholdRead])
def list_user_households(user_id: UUID, db: Session = Depends(get_db)) -> list:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    memberships = db.scalars(
        select(HouseholdMembership)
        .options(selectinload(HouseholdMembership.household))
        .where(HouseholdMembership.user_id == user_id)
        .order_by(HouseholdMembership.created_at)
    ).all()
    return [membership.household for membership in memberships]

