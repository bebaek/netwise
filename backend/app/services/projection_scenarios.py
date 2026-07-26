from collections.abc import Callable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountEvent,
    Household,
    IncomeSource,
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
)
from app.db.session import Base

BASELINE_SCENARIO_NAME = "Baseline"
MAX_SCENARIOS_PER_HOUSEHOLD = 20


class ProjectionScenarioError(ValueError):
    """Base exception for projection-scenario service failures."""


class ProjectionScenarioNotFoundError(ProjectionScenarioError):
    pass


class ProjectionScenarioNameConflictError(ProjectionScenarioError):
    pass


class ProjectionScenarioLimitError(ProjectionScenarioError):
    pass


class BaselineScenarioDeletionError(ProjectionScenarioError):
    pass


def normalize_scenario_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError("Projection scenario name is required")
    if len(normalized) > 120:
        raise ValueError("Projection scenario name must be 120 characters or fewer")
    return normalized


def normalize_scenario_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = description.strip()
    if not normalized:
        return None
    if len(normalized) > 1000:
        raise ValueError("Projection scenario description must be 1000 characters or fewer")
    return normalized


def get_household_scenario(
    db: Session,
    household_id: UUID,
    scenario_id: UUID,
) -> ProjectionScenario:
    scenario = db.scalar(
        select(ProjectionScenario).where(
            ProjectionScenario.id == scenario_id,
            ProjectionScenario.household_id == household_id,
        )
    )
    if scenario is None:
        raise ProjectionScenarioNotFoundError("Projection scenario not found")
    return scenario


def get_baseline_scenario(db: Session, household_id: UUID) -> ProjectionScenario:
    scenario = db.scalar(
        select(ProjectionScenario).where(
            ProjectionScenario.household_id == household_id,
            ProjectionScenario.is_baseline.is_(True),
        )
    )
    if scenario is None:
        raise ProjectionScenarioNotFoundError("Baseline projection scenario not found")
    return scenario


def ensure_baseline_scenario(db: Session, household: Household) -> ProjectionScenario:
    scenario = db.scalar(
        select(ProjectionScenario).where(
            ProjectionScenario.household_id == household.id,
            ProjectionScenario.is_baseline.is_(True),
        )
    )
    if scenario is not None:
        return scenario

    name = BASELINE_SCENARIO_NAME
    suffix = 2
    while db.scalar(
        select(ProjectionScenario.id).where(
            ProjectionScenario.household_id == household.id,
            ProjectionScenario.name == name,
        )
    ) is not None:
        name = f"{BASELINE_SCENARIO_NAME} {suffix}"
        suffix += 1

    scenario = ProjectionScenario(
        household_id=household.id,
        name=name,
        description="Default household projection assumptions",
        is_baseline=True,
    )
    db.add(scenario)
    db.flush()
    _initialize_scenario_assumptions(db, scenario)
    return scenario


def resolve_scenario(
    db: Session,
    household_id: UUID,
    scenario_id: UUID | None,
) -> ProjectionScenario:
    if scenario_id is None:
        return get_baseline_scenario(db, household_id)
    return get_household_scenario(db, household_id, scenario_id)


def ensure_account_assumptions_for_all_scenarios(
    db: Session,
    account: Account,
) -> None:
    scenario_ids = db.scalars(
        select(ProjectionScenario.id).where(ProjectionScenario.household_id == account.household_id)
    ).all()
    existing_scenario_ids = set(
        db.scalars(
            select(ProjectionScenarioAccountAssumption.scenario_id).where(
                ProjectionScenarioAccountAssumption.account_id == account.id
            )
        ).all()
    )
    for scenario_id in scenario_ids:
        if scenario_id in existing_scenario_ids:
            continue
        db.add(
            ProjectionScenarioAccountAssumption(
                scenario_id=scenario_id,
                household_id=account.household_id,
                account_id=account.id,
                expected_annual_yield=account.expected_annual_yield,
                liquidation_expense_rate=account.liquidation_expense_rate,
            )
        )


def ensure_property_assumptions_for_all_scenarios(
    db: Session,
    property_record: RealEstateProperty,
) -> None:
    scenario_ids = db.scalars(
        select(ProjectionScenario.id).where(
            ProjectionScenario.household_id == property_record.household_id
        )
    ).all()
    existing_scenario_ids = set(
        db.scalars(
            select(ProjectionScenarioPropertyAssumption.scenario_id).where(
                ProjectionScenarioPropertyAssumption.property_account_id
                == property_record.account_id
            )
        ).all()
    )
    for scenario_id in scenario_ids:
        if scenario_id in existing_scenario_ids:
            continue
        db.add(
            ProjectionScenarioPropertyAssumption(
                scenario_id=scenario_id,
                household_id=property_record.household_id,
                property_account_id=property_record.account_id,
                expected_appreciation_rate=property_record.expected_appreciation_rate,
                rent_growth_rate=property_record.rent_growth_rate,
                vacancy_rate=property_record.vacancy_rate,
            )
        )


def _initialize_scenario_assumptions(
    db: Session,
    scenario: ProjectionScenario,
) -> None:
    accounts = db.scalars(
        select(Account).where(Account.household_id == scenario.household_id)
    ).all()
    for account in accounts:
        db.add(
            ProjectionScenarioAccountAssumption(
                scenario_id=scenario.id,
                household_id=scenario.household_id,
                account_id=account.id,
                expected_annual_yield=account.expected_annual_yield,
                liquidation_expense_rate=account.liquidation_expense_rate,
            )
        )
    properties = db.scalars(
        select(RealEstateProperty).where(
            RealEstateProperty.household_id == scenario.household_id
        )
    ).all()
    for property_record in properties:
        db.add(
            ProjectionScenarioPropertyAssumption(
                scenario_id=scenario.id,
                household_id=scenario.household_id,
                property_account_id=property_record.account_id,
                expected_appreciation_rate=property_record.expected_appreciation_rate,
                rent_growth_rate=property_record.rent_growth_rate,
                vacancy_rate=property_record.vacancy_rate,
            )
        )


def list_scenarios(db: Session, household_id: UUID) -> list[ProjectionScenario]:
    return list(
        db.scalars(
            select(ProjectionScenario)
            .where(ProjectionScenario.household_id == household_id)
            .order_by(
                ProjectionScenario.is_baseline.desc(),
                ProjectionScenario.created_at,
                ProjectionScenario.name,
            )
        ).all()
    )


def _validate_scenario_creation(db: Session, household_id: UUID, name: str) -> str:
    normalized_name = normalize_scenario_name(name)
    count = db.scalar(
        select(func.count(ProjectionScenario.id)).where(
            ProjectionScenario.household_id == household_id
        )
    )
    if count is not None and count >= MAX_SCENARIOS_PER_HOUSEHOLD:
        raise ProjectionScenarioLimitError(
            f"A household can have at most {MAX_SCENARIOS_PER_HOUSEHOLD} projection scenarios"
        )
    if db.scalar(
        select(ProjectionScenario.id).where(
            ProjectionScenario.household_id == household_id,
            ProjectionScenario.name == normalized_name,
        )
    ) is not None:
        raise ProjectionScenarioNameConflictError(
            "A projection scenario with this name already exists"
        )
    return normalized_name


def _new_scenario(
    db: Session,
    household_id: UUID,
    *,
    name: str,
    description: str | None,
    created_from_scenario_id: UUID | None = None,
) -> ProjectionScenario:
    scenario = ProjectionScenario(
        household_id=household_id,
        name=name,
        description=description,
        is_baseline=False,
        created_from_scenario_id=created_from_scenario_id,
    )
    db.add(scenario)
    db.flush()
    return scenario


def create_scenario(
    db: Session,
    household_id: UUID,
    *,
    name: str,
    description: str | None = None,
) -> ProjectionScenario:
    normalized_name = _validate_scenario_creation(db, household_id, name)
    normalized_description = normalize_scenario_description(description)
    scenario = _new_scenario(
        db,
        household_id,
        name=normalized_name,
        description=normalized_description,
    )
    _initialize_scenario_assumptions(db, scenario)
    return scenario


def _copy_scenario_rows(
    db: Session,
    model: type[Base],
    source: ProjectionScenario,
    target: ProjectionScenario,
    *,
    overrides: Callable[[Base], dict[str, object]] | None = None,
) -> dict[UUID, UUID]:
    copied_ids: dict[UUID, UUID] = {}
    rows = db.scalars(
        select(model).where(getattr(model, "scenario_id") == source.id).order_by(model.id)
    ).all()
    for row in rows:
        values = {
            column.name: getattr(row, column.name)
            for column in model.__table__.columns
            if column.name not in {"id", "scenario_id", "created_at", "updated_at"}
        }
        values["scenario_id"] = target.id
        if overrides is not None:
            values.update(overrides(row))
        copied = model(**values)
        db.add(copied)
        db.flush()
        copied_ids[getattr(row, "id")] = getattr(copied, "id")
    return copied_ids


def _clone_scenario_records(
    db: Session,
    source: ProjectionScenario,
    target: ProjectionScenario,
) -> None:
    _copy_scenario_rows(db, ProjectionSettings, source, target)
    _copy_scenario_rows(db, SpendingItem, source, target)
    income_source_ids = _copy_scenario_rows(db, IncomeSource, source, target)

    def remap_social_security_income(row: Base) -> dict[str, object]:
        income_source_id = getattr(row, "income_source_id")
        cloned_income_source_id = income_source_ids.get(income_source_id)
        if cloned_income_source_id is None:
            raise ProjectionScenarioError(
                "A Social Security estimate references an income source outside its scenario"
            )
        return {"income_source_id": cloned_income_source_id}

    _copy_scenario_rows(
        db,
        SocialSecurityEstimate,
        source,
        target,
        overrides=remap_social_security_income,
    )
    for model in (
        ProjectionTransfer,
        RealEstateSale,
        RealEstateLiquidationStrategy,
        AccountEvent,
        ProjectionScenarioAccountAssumption,
        ProjectionScenarioPropertyAssumption,
    ):
        _copy_scenario_rows(db, model, source, target)


def duplicate_scenario(
    db: Session,
    source: ProjectionScenario,
    *,
    name: str,
    description: str | None = None,
) -> ProjectionScenario:
    normalized_name = _validate_scenario_creation(db, source.household_id, name)
    normalized_description = normalize_scenario_description(description)
    with db.begin_nested():
        scenario = _new_scenario(
            db,
            source.household_id,
            name=normalized_name,
            description=normalized_description,
            created_from_scenario_id=source.id,
        )
        _clone_scenario_records(db, source, scenario)
    return scenario


def update_scenario(
    db: Session,
    scenario: ProjectionScenario,
    *,
    name: str | None = None,
    description: str | None = None,
    update_description: bool = False,
) -> ProjectionScenario:
    if name is not None:
        normalized_name = normalize_scenario_name(name)
        existing_id = db.scalar(
            select(ProjectionScenario.id).where(
                ProjectionScenario.household_id == scenario.household_id,
                ProjectionScenario.name == normalized_name,
                ProjectionScenario.id != scenario.id,
            )
        )
        if existing_id is not None:
            raise ProjectionScenarioNameConflictError(
                "A projection scenario with this name already exists"
            )
        scenario.name = normalized_name
    if update_description:
        scenario.description = normalize_scenario_description(description)
    db.flush()
    return scenario


def delete_scenario(db: Session, scenario: ProjectionScenario) -> None:
    if scenario.is_baseline:
        raise BaselineScenarioDeletionError("The baseline projection scenario cannot be deleted")
    descendants = db.scalars(
        select(ProjectionScenario).where(
            ProjectionScenario.created_from_scenario_id == scenario.id
        )
    ).all()
    for descendant in descendants:
        descendant.created_from_scenario_id = None
    db.delete(scenario)
    db.flush()
