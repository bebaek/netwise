from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Household, ProjectionScenario

BASELINE_SCENARIO_NAME = "Baseline"
MAX_SCENARIOS_PER_HOUSEHOLD = 20


class ProjectionScenarioError(Exception):
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
    return scenario


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
