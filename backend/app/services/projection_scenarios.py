from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    Household,
    ProjectionScenario,
    ProjectionScenarioAccountAssumption,
    ProjectionScenarioPropertyAssumption,
    RealEstateProperty,
)

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


def create_scenario(
    db: Session,
    household_id: UUID,
    *,
    name: str,
    description: str | None = None,
) -> ProjectionScenario:
    normalized_name = normalize_scenario_name(name)
    normalized_description = normalize_scenario_description(description)
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

    scenario = ProjectionScenario(
        household_id=household_id,
        name=normalized_name,
        description=normalized_description,
        is_baseline=False,
    )
    db.add(scenario)
    db.flush()
    _initialize_scenario_assumptions(db, scenario)
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
    db.delete(scenario)
    db.flush()
