from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import (
    clear_session_cookie,
    create_user_session,
    get_optional_current_user,
    hash_password,
    session_token_digest,
    set_session_cookie,
    validate_email,
    verify_user_password,
)
from app.db.models import Household, HouseholdMembership, User, UserSession
from app.db.session import get_db
from app.schemas.auth import AuthLogin, AuthRegister, AuthStatusRead
from app.schemas.user import UserRead
from app.services.projection_scenarios import ensure_baseline_scenario

router = APIRouter(prefix="/auth", tags=["auth"])


def _setup_required(db: Session) -> bool:
    return db.scalar(select(User.id).where(User.password_hash.is_not(None)).limit(1)) is None


def _validated_email(email: str) -> str:
    try:
        return validate_email(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def _set_up_initial_households(db: Session, user: User, settings: Settings) -> None:
    households = list(db.scalars(select(Household).order_by(Household.created_at)).all())
    if not households and settings.single_household_mode:
        household = Household(name="Home")
        db.add(household)
        db.flush()
        households = [household]

    for household in households:
        ensure_baseline_scenario(db, household)
        existing_membership = db.scalar(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household.id,
                HouseholdMembership.user_id == user.id,
            )
        )
        if existing_membership is None:
            db.add(
                HouseholdMembership(
                    household_id=household.id,
                    user_id=user.id,
                    role="owner",
                )
            )
        else:
            existing_membership.role = "owner"


@router.get("/status", response_model=AuthStatusRead)
def get_auth_status(
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthStatusRead:
    return AuthStatusRead(
        setup_required=_setup_required(db),
        public_signup_enabled=settings.public_signup,
        user=UserRead.model_validate(user) if user is not None else None,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: AuthRegister,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    initial_setup = _setup_required(db)
    if not initial_setup and not settings.public_signup:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public signup is disabled")

    email = _validated_email(payload.email)
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Display name is required",
        )

    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        if existing_user.password_hash is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
        user = existing_user
        user.display_name = display_name
        user.password_hash = hash_password(payload.password)
    else:
        user = User(
            display_name=display_name,
            email=email,
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.flush()

    if initial_setup:
        _set_up_initial_households(db, user, settings)

    _, token = create_user_session(db, user, settings)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from exc
    db.refresh(user)
    set_session_cookie(response, token, settings)
    return user


@router.post("/login", response_model=UserRead)
def login(
    payload: AuthLogin,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    email = _validated_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    password_matches = verify_user_password(
        payload.password,
        user.password_hash if user is not None else None,
    )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    _, token = create_user_session(db, user, settings)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, token, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        session = db.scalar(
            select(UserSession).where(UserSession.token_digest == session_token_digest(token))
        )
        if session is not None:
            db.delete(session)
            db.commit()
    clear_session_cookie(response, settings)
