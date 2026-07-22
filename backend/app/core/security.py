from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets

from fastapi import Depends, HTTPException, Request, Response, status
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import User, UserSession
from app.db.session import get_db

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash(secrets.token_urlsafe(32))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> str:
    normalized = normalize_email(email)
    local, separator, domain = normalized.partition("@")
    if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Enter a valid email address")
    return normalized


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_user_password(password: str, password_hash: str | None) -> bool:
    candidate_hash = password_hash or _dummy_password_hash
    verified = _password_hash.verify(password, candidate_hash)
    return password_hash is not None and verified


def session_token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_user_session(db: Session, user: User, settings: Settings) -> tuple[UserSession, str]:
    token = secrets.token_urlsafe(32)
    session = UserSession(
        user_id=user.id,
        token_digest=session_token_digest(token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.auth_session_days),
    )
    db.add(session)
    return session, token


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None

    session = db.scalar(
        select(UserSession).where(UserSession.token_digest == session_token_digest(token))
    )
    if session is None:
        return None
    if _as_utc(session.expires_at) <= datetime.now(UTC):
        db.delete(session)
        db.commit()
        return None
    return session.user


def require_authenticated_user(
    user: User | None = Depends(get_optional_current_user),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
