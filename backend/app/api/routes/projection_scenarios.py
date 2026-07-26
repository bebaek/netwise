from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    Household,
    ProjectionScenario,
    ProjectionScenarioAccountAssumption,
    ProjectionScenarioPropertyAssumption,
    RealEstateProperty,
)
from app.db.session import get_db
from app.schemas.projection_scenario import (
    ProjectionScenarioAccountAssumptionRead,
    ProjectionScenarioAccountAssumptionUpdate,
    ProjectionScenarioCreate,
    ProjectionScenarioDuplicate,
    ProjectionScenarioPropertyAssumptionRead,
    ProjectionScenarioPropertyAssumptionUpdate,
    ProjectionScenarioRead,
    ProjectionScenarioUpdate,
)
from app.services.projection_scenarios import (
    BaselineScenarioDeletionError,
    ProjectionScenarioLimitError,
    ProjectionScenarioNameConflictError,
    ProjectionScenarioNotFoundError,
    create_scenario,
    delete_scenario,
    duplicate_scenario,
    ensure_account_assumptions_for_all_scenarios,
    ensure_property_assumptions_for_all_scenarios,
    get_household_scenario,
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
        if payload.source_scenario_id is None:
            scenario = create_scenario(
                db,
                household_id,
                name=payload.name,
                description=payload.description,
            )
        else:
            source = get_household_scenario(db, household_id, payload.source_scenario_id)
            scenario = duplicate_scenario(
                db,
                source,
                name=payload.name,
                description=payload.description,
            )
    except ProjectionScenarioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectionScenarioNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProjectionScenarioLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _commit_or_conflict(db)
    db.refresh(scenario)
    return scenario


@router.post(
    "/projection-scenarios/{scenario_id}/duplicate",
    response_model=ProjectionScenarioRead,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_projection_scenario(
    scenario_id: UUID,
    payload: ProjectionScenarioDuplicate,
    db: Session = Depends(get_db),
) -> ProjectionScenario:
    source = _get_scenario_or_404(db, scenario_id)
    try:
        scenario = duplicate_scenario(
            db,
            source,
            name=payload.name,
            description=payload.description,
        )
    except ProjectionScenarioNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProjectionScenarioLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
    except ProjectionScenarioNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _commit_or_conflict(db)
    db.refresh(scenario)
    return scenario


@router.get(
    "/projection-scenarios/{scenario_id}/account-assumptions",
    response_model=list[ProjectionScenarioAccountAssumptionRead],
)
def list_account_assumptions(
    scenario_id: UUID,
    db: Session = Depends(get_db),
) -> list[ProjectionScenarioAccountAssumption]:
    scenario = _get_scenario_or_404(db, scenario_id)
    return list(
        db.scalars(
            select(ProjectionScenarioAccountAssumption)
            .where(ProjectionScenarioAccountAssumption.scenario_id == scenario.id)
            .order_by(ProjectionScenarioAccountAssumption.account_id)
        ).all()
    )


@router.put(
    "/projection-scenarios/{scenario_id}/account-assumptions/{account_id}",
    response_model=ProjectionScenarioAccountAssumptionRead,
)
def update_account_assumption(
    scenario_id: UUID,
    account_id: UUID,
    payload: ProjectionScenarioAccountAssumptionUpdate,
    db: Session = Depends(get_db),
) -> ProjectionScenarioAccountAssumption:
    scenario = _get_scenario_or_404(db, scenario_id)
    account = db.get(Account, account_id)
    if account is None or account.household_id != scenario.household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    ensure_account_assumptions_for_all_scenarios(db, account)
    db.flush()
    assumption = db.scalar(
        select(ProjectionScenarioAccountAssumption).where(
            ProjectionScenarioAccountAssumption.scenario_id == scenario.id,
            ProjectionScenarioAccountAssumption.account_id == account.id,
        )
    )
    if assumption is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assumption not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(assumption, field, value)
    db.commit()
    db.refresh(assumption)
    return assumption


@router.get(
    "/projection-scenarios/{scenario_id}/property-assumptions",
    response_model=list[ProjectionScenarioPropertyAssumptionRead],
)
def list_property_assumptions(
    scenario_id: UUID,
    db: Session = Depends(get_db),
) -> list[ProjectionScenarioPropertyAssumption]:
    scenario = _get_scenario_or_404(db, scenario_id)
    return list(
        db.scalars(
            select(ProjectionScenarioPropertyAssumption)
            .where(ProjectionScenarioPropertyAssumption.scenario_id == scenario.id)
            .order_by(ProjectionScenarioPropertyAssumption.property_account_id)
        ).all()
    )


@router.put(
    "/projection-scenarios/{scenario_id}/property-assumptions/{property_account_id}",
    response_model=ProjectionScenarioPropertyAssumptionRead,
)
def update_property_assumption(
    scenario_id: UUID,
    property_account_id: UUID,
    payload: ProjectionScenarioPropertyAssumptionUpdate,
    db: Session = Depends(get_db),
) -> ProjectionScenarioPropertyAssumption:
    scenario = _get_scenario_or_404(db, scenario_id)
    property_record = db.scalar(
        select(RealEstateProperty).where(
            RealEstateProperty.account_id == property_account_id,
            RealEstateProperty.household_id == scenario.household_id,
        )
    )
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    ensure_property_assumptions_for_all_scenarios(db, property_record)
    db.flush()
    assumption = db.scalar(
        select(ProjectionScenarioPropertyAssumption).where(
            ProjectionScenarioPropertyAssumption.scenario_id == scenario.id,
            ProjectionScenarioPropertyAssumption.property_account_id == property_account_id,
        )
    )
    if assumption is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assumption not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(assumption, field, value)
    db.commit()
    db.refresh(assumption)
    return assumption


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
