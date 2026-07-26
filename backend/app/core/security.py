from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import ApiToken, User, UserSession
from app.db.session import get_db

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash(secrets.token_urlsafe(32))
_bearer_scheme = HTTPBearer(auto_error=False)


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


def api_token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_api_token_secret() -> str:
    return f"nwt_{secrets.token_urlsafe(32)}"


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


def _api_token_from_request(request: Request, db: Session) -> ApiToken | None:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return None
    scheme, separator, secret = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_token = db.scalar(
        select(ApiToken).where(ApiToken.token_digest == api_token_digest(secret))
    )
    now = datetime.now(UTC)
    if (
        api_token is None
        or api_token.revoked_at is not None
        or _as_utc(api_token.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_token


def _authorize_api_token_request(request: Request, api_token: ApiToken) -> None:
    path = request.url.path.rstrip("/")
    blocked_path = (
        path.startswith("/auth")
        or path.startswith("/api-tokens")
        or path.startswith("/users")
        or path.startswith("/imports")
        or "/members" in path
        or path.endswith("/export")
    )
    if blocked_path:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API tokens cannot access this endpoint",
        )

    is_read = request.method in {"GET", "HEAD", "OPTIONS"}
    is_projection_run = request.method == "POST" and path.endswith("/projection-comparison")
    is_snapshot_write = request.method == "POST" and path.endswith("/snapshot-batch")
    required_scope = None
    if is_read:
        required_scope = "finance:read"
    elif is_projection_run:
        required_scope = "projections:run"
    elif is_snapshot_write:
        required_scope = "finance:write"
    if required_scope is None or required_scope not in api_token.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API token scope does not permit this action",
        )


def require_authenticated_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _bearer: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    api_token = _api_token_from_request(request, db)
    if api_token is not None:
        request.state.api_token_audit_context = {
            "api_token_id": api_token.id,
            "user_id": api_token.user_id,
            "household_id": api_token.household_id,
            "token_name": api_token.name,
            "token_prefix": api_token.token_prefix,
        }
        _authorize_api_token_request(request, api_token)
        request.state.api_token = api_token
        api_token.last_used_at = datetime.now(UTC)
        db.commit()
        return api_token.user

    request.state.api_token = None
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        session = db.scalar(
            select(UserSession).where(UserSession.token_digest == session_token_digest(token))
        )
        if session is not None and _as_utc(session.expires_at) > datetime.now(UTC):
            return session.user
        if session is not None:
            db.delete(session)
            db.commit()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
