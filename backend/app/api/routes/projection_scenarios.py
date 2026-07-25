from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Household, ProjectionScenario
from app.db.session import get_db
from app.schemas.projection_scenario import (
    ProjectionScenarioCreate,
    ProjectionScenarioRead,
    ProjectionScenarioUpdate,
)
from app.services.projection_scenarios import (
    BaselineScenarioDeletionError,
    ProjectionScenarioLimitError,
    ProjectionScenarioNameConflictError,
    create_scenario,
    delete_scenario,
    list_scenarios,
    update_scenario,
)

router = APIRouter(tags=["projection-scenarios"])


def _get_scenario_or_404(db: Session, scenario_id: UUID) -> ProjectionScenario:
    scenario = db.get(ProjectionScenario, scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projection scenario not found",
        )
    return scenario


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Projection scenario conflicts with an existing scenario",
        ) from exc


@router.get(
    "/households/{household_id}/projection-scenarios",
    response_model=list[ProjectionScenarioRead],
)
def list_projection_scenarios(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[ProjectionScenario]:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    return list_scenarios(db, household_id)


@router.post(
    "/households/{household_id}/projection-scenarios",
    response_model=ProjectionScenarioRead,
    status_code=status.HTTP_201_CREATED,
)
def create_projection_scenario(
    household_id: UUID,
    payload: ProjectionScenarioCreate,
    db: Session = Depends(get_db),
) -> ProjectionScenario:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        scenario = create_scenario(
            db,
            household_id,
            name=payload.name,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProjectionScenarioNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProjectionScenarioLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _commit_or_conflict(db)
    db.refresh(scenario)
    return scenario


@router.get(
    "/projection-scenarios/{scenario_id}",
    response_model=ProjectionScenarioRead,
)
def get_projection_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
) -> ProjectionScenario:
    return _get_scenario_or_404(db, scenario_id)


@router.patch(
    "/projection-scenarios/{scenario_id}",
    response_model=ProjectionScenarioRead,
)
def patch_projection_scenario(
    scenario_id: UUID,
    payload: ProjectionScenarioUpdate,
    db: Session = Depends(get_db),
) -> ProjectionScenario:
    scenario = _get_scenario_or_404(db, scenario_id)
    if "name" in payload.model_fields_set and payload.name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Projection scenario name cannot be null",
        )
    try:
        update_scenario(
            db,
            scenario,
            name=payload.name,
            description=payload.description,
            update_description="description" in payload.model_fields_set,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProjectionScenarioNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _commit_or_conflict(db)
    db.refresh(scenario)
    return scenario


@router.delete(
    "/projection-scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_projection_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    scenario = _get_scenario_or_404(db, scenario_id)
    try:
        delete_scenario(db, scenario)
    except BaselineScenarioDeletionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
