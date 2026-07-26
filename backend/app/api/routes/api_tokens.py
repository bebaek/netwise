from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import get_household_membership
from app.core.security import (
    api_token_digest,
    create_api_token_secret,
    get_optional_current_user,
)
from app.db.models import ApiToken, ApiTokenAuditEvent, User
from app.db.session import get_db
from app.schemas.api_token import (
    ApiTokenAuditEventRead,
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenRead,
)

router = APIRouter(prefix="/api-tokens", tags=["api-tokens"])


def require_session_user(
    user: User | None = Depends(get_optional_current_user),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A browser session is required to manage API tokens",
        )
    return user


@router.get("", response_model=list[ApiTokenRead])
def list_api_tokens(
    db: Session = Depends(get_db),
    user: User = Depends(require_session_user),
) -> list[ApiToken]:
    return list(
        db.scalars(
            select(ApiToken)
            .where(ApiToken.user_id == user.id)
            .order_by(ApiToken.created_at.desc())
        ).all()
    )


@router.post("", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
def create_api_token(
    payload: ApiTokenCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_session_user),
) -> ApiTokenCreated:
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Token name is required",
        )
    if get_household_membership(db, user.id, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    scopes = list(dict.fromkeys(payload.scopes))
    if not scopes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one API token scope is required",
        )

    secret = create_api_token_secret()
    api_token = ApiToken(
        user_id=user.id,
        household_id=payload.household_id,
        name=name,
        token_prefix=secret[:12],
        token_digest=api_token_digest(secret),
        scopes=scopes,
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
    )
    db.add(api_token)
    db.commit()
    db.refresh(api_token)
    token_data = ApiTokenRead.model_validate(api_token).model_dump()
    return ApiTokenCreated(**token_data, token=secret)


@router.get("/audit-events", response_model=list[ApiTokenAuditEventRead])
def list_api_token_audit_events(
    household_id: UUID,
    token_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_session_user),
) -> list[ApiTokenAuditEvent]:
    statement = (
        select(ApiTokenAuditEvent)
        .where(
            ApiTokenAuditEvent.user_id == user.id,
            ApiTokenAuditEvent.household_id == household_id,
        )
        .order_by(ApiTokenAuditEvent.created_at.desc())
        .limit(limit)
    )
    if token_id is not None:
        statement = statement.where(ApiTokenAuditEvent.api_token_id == token_id)
    return list(db.scalars(statement).all())


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_token(
    token_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_session_user),
) -> None:
    api_token = db.scalar(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user.id)
    )
    if api_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found")
    if api_token.revoked_at is None:
        api_token.revoked_at = datetime.now(UTC)
        db.commit()
