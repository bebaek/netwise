from collections.abc import Mapping
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_authenticated_user
from app.db.models import (
    Account,
    AccountEvent,
    AnnualTaxRecord,
    BalanceSnapshot,
    HouseholdMembership,
    HouseholdPerson,
    IncomeSource,
    MortgageProfile,
    MembershipRole,
    ProjectionScenario,
    ProjectionTransfer,
    RealEstateProperty,
    RealEstateSale,
    SocialSecurityEstimate,
    SpendingItem,
    User,
)
from app.db.session import get_db

_READ_METHODS = {"GET", "HEAD", "OPTIONS"}
_WRITE_ROLES = {"owner", "admin", "member"}
_ADMIN_ROLES = {"owner", "admin"}
_ALL_ROLES = {role.value for role in MembershipRole}

_RESOURCE_MODELS: Mapping[str, type] = {
    "account_id": Account,
    "property_account_id": Account,
    "liability_account_id": Account,
    "snapshot_id": BalanceSnapshot,
    "event_id": AccountEvent,
    "sale_id": RealEstateSale,
    "property_id": RealEstateProperty,
    "mortgage_id": MortgageProfile,
    "person_id": HouseholdPerson,
    "estimate_id": SocialSecurityEstimate,
    "scenario_id": ProjectionScenario,
    "projection_transfer_id": ProjectionTransfer,
    "spending_item_id": SpendingItem,
    "income_source_id": IncomeSource,
    "tax_record_id": AnnualTaxRecord,
}


def get_household_membership(
    db: Session,
    user_id: UUID,
    household_id: UUID,
) -> HouseholdMembership | None:
    return db.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == user_id,
        )
    )


def require_household_role(
    db: Session,
    user: User,
    household_id: UUID,
    allowed_roles: set[str],
) -> HouseholdMembership:
    membership = get_household_membership(db, user.id, household_id)
    if membership is None:
        # Do not reveal whether a household exists to a non-member.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    if membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your household role does not permit this action",
        )
    return membership


def _uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _resource_household_id(db: Session, values: Mapping[str, object]) -> UUID | None:
    for parameter_name, model in _RESOURCE_MODELS.items():
        resource_id = _uuid(values.get(parameter_name))
        if resource_id is None:
            continue
        resource = db.get(model, resource_id)
        if resource is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return resource.household_id
    return None


async def _request_body_values(request: Request) -> dict[str, object]:
    try:
        body = await request.json()
    except Exception:  # Invalid JSON is reported by FastAPI's body validation.
        return {}
    return body if isinstance(body, dict) else {}


def _requires_admin_role(request: Request) -> bool:
    path = request.url.path
    return (
        path.startswith("/imports/")
        or path.endswith("/export")
        or "/members" in path and request.method not in _READ_METHODS
    )


async def authorize_household_request(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_authenticated_user),
) -> HouseholdMembership | None:
    path = request.url.path.rstrip("/")
    if path == "/households" and request.method in {"GET", "POST"}:
        return None

    path_values: dict[str, object] = dict(request.path_params)
    household_id = _uuid(path_values.get("household_id"))
    if household_id is None:
        household_id = _resource_household_id(db, path_values)

    if household_id is None and request.method not in _READ_METHODS:
        body_values = await _request_body_values(request)
        household_id = _uuid(body_values.get("household_id"))
        if household_id is None:
            household_id = _resource_household_id(db, body_values)

    if household_id is None and request.method in _READ_METHODS:
        query_values: dict[str, object] = dict(request.query_params)
        household_id = _uuid(query_values.get("household_id"))
        if household_id is None:
            household_id = _resource_household_id(db, query_values)
    if household_id is None:
        # Every route using this dependency must resolve to a household. Fail closed.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to authorize household access",
        )

    if _requires_admin_role(request):
        allowed_roles = _ADMIN_ROLES
    elif request.method in _READ_METHODS:
        allowed_roles = _ALL_ROLES
    else:
        allowed_roles = _WRITE_ROLES
    return require_household_role(db, user, household_id, allowed_roles)
