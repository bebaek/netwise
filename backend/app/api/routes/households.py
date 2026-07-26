from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.authorization import get_household_membership
from app.core.config import Settings, get_settings
from app.core.security import require_authenticated_user
from app.db.models import (
    Account,
    AccountEvent,
    AnnualTaxRecord,
    BalanceSnapshot,
    Household,
    HouseholdMembership,
    HouseholdPerson,
    IncomeSource,
    MembershipRole,
    MortgageProfile,
    ProjectionScenario,
    ProjectionScenarioAccountAssumption,
    ProjectionScenarioPropertyAssumption,
    ProjectionSettings,
    ProjectionTransfer,
    RealEstateLiquidationStrategy,
    RealEstateProperty,
    RealEstateSale,
    SocialSecurityEstimate,
    SpendingItem,
    User,
)
from app.db.session import get_db
from app.schemas.account import (
    AccountEventRead,
    BalanceSnapshotBatchCreate,
    BalanceSnapshotBatchRead,
    HouseholdBalanceSnapshotRead,
)
from app.schemas.household import HouseholdCreate, HouseholdRead
from app.schemas.user import HouseholdMembershipCreate, HouseholdMembershipRead
from app.services.projection_scenarios import (
    ProjectionScenarioNotFoundError,
    ensure_baseline_scenario,
    resolve_scenario,
)

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


def require_admin_tools_enabled(settings: Settings = Depends(get_settings)) -> None:
    if not settings.enable_admin_tools:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin tools are disabled"
        )


def _model_export(model: object, fields: tuple[str, ...]) -> dict:
    return {field: getattr(model, field) for field in fields}


_HOUSEHOLD_FIELDS = ("id", "name", "created_at", "updated_at")
_USER_FIELDS = ("id", "display_name", "email", "created_at", "updated_at")
_MEMBERSHIP_FIELDS = ("id", "household_id", "user_id", "role", "created_at")
_ACCOUNT_FIELDS = (
    "id",
    "household_id",
    "name",
    "institution_name",
    "account_kind",
    "category",
    "liquidity_class",
    "retirement_tax_treatment",
    "expected_annual_yield",
    "liquidation_expense_rate",
    "currency",
    "is_active",
    "created_at",
    "updated_at",
)
_SNAPSHOT_FIELDS = (
    "id",
    "household_id",
    "account_id",
    "as_of_date",
    "balance",
    "currency",
    "source",
    "confidence_level",
    "created_at",
)
_ACCOUNT_EVENT_FIELDS = (
    "id",
    "household_id",
    "account_id",
    "event_date",
    "amount",
    "currency",
    "event_type",
    "description",
    "projection_behavior",
    "scenario_id",
    "created_at",
    "updated_at",
)
_REAL_ESTATE_FIELDS = (
    "id",
    "household_id",
    "account_id",
    "property_type",
    "purchase_date",
    "purchase_price",
    "adjusted_tax_basis",
    "down_payment",
    "expected_appreciation_rate",
    "property_tax_annual",
    "insurance_annual",
    "tax_and_insurance_annual",
    "maintenance_rate",
    "hoa_monthly",
    "is_rental",
    "rental_start_date",
    "monthly_market_rent",
    "other_monthly_income",
    "rent_growth_rate",
    "vacancy_rate",
    "management_fee_rate",
    "utilities_annual",
    "other_operating_expense_annual",
    "capital_reserve_rate",
    "rental_deposit_account_id",
    "created_at",
    "updated_at",
)
_MORTGAGE_FIELDS = (
    "id",
    "household_id",
    "liability_account_id",
    "property_account_id",
    "original_principal",
    "interest_rate",
    "term_months",
    "start_date",
    "monthly_payment",
    "rate_type",
    "created_at",
    "updated_at",
)
_INCOME_SOURCE_FIELDS = (
    "id",
    "household_id",
    "scenario_id",
    "name",
    "income_type",
    "amount",
    "currency",
    "frequency",
    "start_date",
    "end_date",
    "growth_rate",
    "deposit_account_id",
    "created_at",
    "updated_at",
)
_PROJECTION_TRANSFER_FIELDS = (
    "id",
    "household_id",
    "scenario_id",
    "name",
    "from_account_id",
    "to_account_id",
    "annual_amount",
    "start_date",
    "end_date",
    "growth_rate",
    "created_at",
    "updated_at",
)
_SPENDING_ITEM_FIELDS = (
    "id",
    "household_id",
    "scenario_id",
    "name",
    "category",
    "annual_amount",
    "retirement_annual_amount",
    "growth_rate",
    "created_at",
    "updated_at",
)
_ANNUAL_TAX_RECORD_FIELDS = (
    "id",
    "household_id",
    "tax_year",
    "gross_income",
    "total_taxes_paid",
    "refund_or_amount_due",
    "notes",
    "created_at",
    "updated_at",
)


_SCENARIO_FIELDS = tuple(column.name for column in ProjectionScenario.__table__.columns)
_ACCOUNT_ASSUMPTION_FIELDS = tuple(
    column.name for column in ProjectionScenarioAccountAssumption.__table__.columns
)
_PROPERTY_ASSUMPTION_FIELDS = tuple(
    column.name for column in ProjectionScenarioPropertyAssumption.__table__.columns
)
_PROJECTION_SETTINGS_FIELDS = tuple(column.name for column in ProjectionSettings.__table__.columns)
_SOCIAL_SECURITY_FIELDS = tuple(
    column.name for column in SocialSecurityEstimate.__table__.columns
)
_REAL_ESTATE_SALE_FIELDS = tuple(column.name for column in RealEstateSale.__table__.columns)
_LIQUIDATION_STRATEGY_FIELDS = tuple(
    column.name for column in RealEstateLiquidationStrategy.__table__.columns
)
_HOUSEHOLD_PERSON_FIELDS = tuple(column.name for column in HouseholdPerson.__table__.columns)


@router.post("", response_model=HouseholdRead, status_code=status.HTTP_201_CREATED)
def create_household(
    payload: HouseholdCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> Household:
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Household name is required"
        )

    if payload.owner_user_id is not None and payload.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A household can only be created for the authenticated user",
        )

    household = Household(name=name)
    db.add(household)
    db.flush()
    ensure_baseline_scenario(db, household)
    db.add(
        HouseholdMembership(
            household_id=household.id,
            user_id=current_user.id,
            role="owner",
        )
    )
    db.commit()
    db.refresh(household)
    return household


@router.get("", response_model=list[HouseholdRead])
def list_households(
    request: Request,
    user_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> list[Household]:
    if user_id is not None and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot list another user's households",
        )

    statement = (
        select(Household)
        .join(HouseholdMembership, HouseholdMembership.household_id == Household.id)
        .where(HouseholdMembership.user_id == current_user.id)
        .order_by(Household.created_at)
    )
    api_token = getattr(request.state, "api_token", None)
    if api_token is not None:
        statement = statement.where(Household.id == api_token.household_id)
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
        .order_by(
            BalanceSnapshot.as_of_date.desc(), Account.name, BalanceSnapshot.created_at.desc()
        )
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


@router.get("/{household_id}/events", response_model=list[AccountEventRead])
def list_household_account_events(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[AccountEvent]:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        scenario = resolve_scenario(db, household_id, scenario_id)
    except ProjectionScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projection scenario not found",
        ) from exc

    return list(
        db.scalars(
            select(AccountEvent)
            .where(
                AccountEvent.household_id == household_id,
                or_(AccountEvent.scenario_id.is_(None), AccountEvent.scenario_id == scenario.id),
            )
            .order_by(AccountEvent.event_date.desc(), AccountEvent.created_at.desc())
        ).all()
    )


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
    current_user: User = Depends(require_authenticated_user),
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

    role = validate_membership_role(payload.role)
    actor_membership = get_household_membership(db, current_user.id, household_id)
    if role == MembershipRole.owner and actor_membership.role != MembershipRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can grant the owner role",
        )

    membership = HouseholdMembership(
        household_id=household_id,
        user_id=payload.user_id,
        role=role,
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
    current_user: User = Depends(require_authenticated_user),
) -> None:
    membership = db.scalars(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    actor_membership = get_household_membership(db, current_user.id, household_id)
    if membership.role == MembershipRole.owner:
        if actor_membership.role != MembershipRole.owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an owner can remove another owner",
            )
        owner_count = db.scalar(
            select(func.count())
            .select_from(HouseholdMembership)
            .where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.role == MembershipRole.owner,
            )
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A household must retain at least one owner",
            )

    db.delete(membership)
    db.commit()


@router.get("/{household_id}/export")
def export_household(
    household_id: UUID,
    _: None = Depends(require_admin_tools_enabled),
    db: Session = Depends(get_db),
) -> dict:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    memberships = list(
        db.scalars(
            select(HouseholdMembership)
            .options(selectinload(HouseholdMembership.user))
            .where(HouseholdMembership.household_id == household_id)
            .order_by(HouseholdMembership.created_at)
        ).all()
    )
    accounts = list(
        db.scalars(
            select(Account).where(Account.household_id == household_id).order_by(Account.name)
        ).all()
    )

    export = {
        "schema": "netwise.household_export.v1",
        "exported_at": datetime.now(UTC),
        "household": _model_export(household, _HOUSEHOLD_FIELDS),
        "members": [
            {
                **_model_export(membership, _MEMBERSHIP_FIELDS),
                "user": _model_export(membership.user, _USER_FIELDS) if membership.user else None,
            }
            for membership in memberships
        ],
        "accounts": [_model_export(account, _ACCOUNT_FIELDS) for account in accounts],
        "projection_scenarios": [
            _model_export(scenario, _SCENARIO_FIELDS)
            for scenario in db.scalars(
                select(ProjectionScenario)
                .where(ProjectionScenario.household_id == household_id)
                .order_by(
                    ProjectionScenario.is_baseline.desc(),
                    ProjectionScenario.created_at,
                )
            ).all()
        ],
        "projection_scenario_account_assumptions": [
            _model_export(assumption, _ACCOUNT_ASSUMPTION_FIELDS)
            for assumption in db.scalars(
                select(ProjectionScenarioAccountAssumption)
                .where(ProjectionScenarioAccountAssumption.household_id == household_id)
                .order_by(
                    ProjectionScenarioAccountAssumption.scenario_id,
                    ProjectionScenarioAccountAssumption.account_id,
                )
            ).all()
        ],
        "projection_scenario_property_assumptions": [
            _model_export(assumption, _PROPERTY_ASSUMPTION_FIELDS)
            for assumption in db.scalars(
                select(ProjectionScenarioPropertyAssumption)
                .where(ProjectionScenarioPropertyAssumption.household_id == household_id)
                .order_by(
                    ProjectionScenarioPropertyAssumption.scenario_id,
                    ProjectionScenarioPropertyAssumption.property_account_id,
                )
            ).all()
        ],
        "snapshots": [
            _model_export(snapshot, _SNAPSHOT_FIELDS)
            for snapshot in db.scalars(
                select(BalanceSnapshot)
                .where(BalanceSnapshot.household_id == household_id)
                .order_by(BalanceSnapshot.as_of_date, BalanceSnapshot.account_id)
            ).all()
        ],
        "account_events": [
            _model_export(event, _ACCOUNT_EVENT_FIELDS)
            for event in db.scalars(
                select(AccountEvent)
                .where(AccountEvent.household_id == household_id)
                .order_by(AccountEvent.event_date, AccountEvent.account_id, AccountEvent.created_at)
            ).all()
        ],
        "real_estate_properties": [
            _model_export(property_record, _REAL_ESTATE_FIELDS)
            for property_record in db.scalars(
                select(RealEstateProperty)
                .where(RealEstateProperty.household_id == household_id)
                .order_by(RealEstateProperty.created_at)
            ).all()
        ],
        "mortgage_profiles": [
            _model_export(mortgage, _MORTGAGE_FIELDS)
            for mortgage in db.scalars(
                select(MortgageProfile)
                .where(MortgageProfile.household_id == household_id)
                .order_by(MortgageProfile.created_at)
            ).all()
        ],
        "household_people": [
            _model_export(person, _HOUSEHOLD_PERSON_FIELDS)
            for person in db.scalars(
                select(HouseholdPerson)
                .where(HouseholdPerson.household_id == household_id)
                .order_by(HouseholdPerson.created_at)
            ).all()
        ],
        "projection_settings": [
            _model_export(settings, _PROJECTION_SETTINGS_FIELDS)
            for settings in db.scalars(
                select(ProjectionSettings)
                .where(ProjectionSettings.household_id == household_id)
                .order_by(ProjectionSettings.scenario_id)
            ).all()
        ],
        "income_sources": [
            _model_export(income_source, _INCOME_SOURCE_FIELDS)
            for income_source in db.scalars(
                select(IncomeSource)
                .where(IncomeSource.household_id == household_id)
                .order_by(IncomeSource.scenario_id, IncomeSource.name)
            ).all()
        ],
        "projection_transfers": [
            _model_export(projection_transfer, _PROJECTION_TRANSFER_FIELDS)
            for projection_transfer in db.scalars(
                select(ProjectionTransfer)
                .where(ProjectionTransfer.household_id == household_id)
                .order_by(
                    ProjectionTransfer.scenario_id,
                    ProjectionTransfer.name,
                    ProjectionTransfer.created_at,
                )
            ).all()
        ],
        "spending_items": [
            _model_export(spending_item, _SPENDING_ITEM_FIELDS)
            for spending_item in db.scalars(
                select(SpendingItem)
                .where(SpendingItem.household_id == household_id)
                .order_by(SpendingItem.scenario_id, SpendingItem.category, SpendingItem.name)
            ).all()
        ],
        "social_security_estimates": [
            _model_export(estimate, _SOCIAL_SECURITY_FIELDS)
            for estimate in db.scalars(
                select(SocialSecurityEstimate)
                .where(SocialSecurityEstimate.household_id == household_id)
                .order_by(SocialSecurityEstimate.scenario_id, SocialSecurityEstimate.person_id)
            ).all()
        ],
        "real_estate_sales": [
            _model_export(sale, _REAL_ESTATE_SALE_FIELDS)
            for sale in db.scalars(
                select(RealEstateSale)
                .where(RealEstateSale.household_id == household_id)
                .order_by(RealEstateSale.scenario_id, RealEstateSale.sale_date)
            ).all()
        ],
        "real_estate_liquidation_strategies": [
            _model_export(strategy, _LIQUIDATION_STRATEGY_FIELDS)
            for strategy in db.scalars(
                select(RealEstateLiquidationStrategy)
                .where(RealEstateLiquidationStrategy.household_id == household_id)
                .order_by(
                    RealEstateLiquidationStrategy.scenario_id,
                    RealEstateLiquidationStrategy.priority,
                )
            ).all()
        ],
        "annual_tax_records": [
            _model_export(tax_record, _ANNUAL_TAX_RECORD_FIELDS)
            for tax_record in db.scalars(
                select(AnnualTaxRecord)
                .where(AnnualTaxRecord.household_id == household_id)
                .order_by(AnnualTaxRecord.tax_year)
            ).all()
        ],
    }
    return jsonable_encoder(export, custom_encoder={Decimal: str})


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
    missing_account_ids = [
        str(account_id) for account_id in account_ids if account_id not in accounts
    ]
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
