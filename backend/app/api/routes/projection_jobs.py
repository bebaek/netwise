from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Household
from app.db.session import get_db
from app.schemas.projection_job import ProjectionJobRead, ProjectionJobRequest
from app.services.projection_jobs import (
    create_projection_job,
    get_projection_job,
    read_projection_job,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.post(
    "/{household_id}/projection-jobs",
    response_model=ProjectionJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_projection(
    household_id: UUID,
    payload: ProjectionJobRequest,
    db: Session = Depends(get_db),
) -> ProjectionJobRead:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    try:
        return create_projection_job(db, household_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{household_id}/projection-jobs/{job_id}",
    response_model=ProjectionJobRead,
)
def get_projection_job_status(
    household_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> ProjectionJobRead:
    job = get_projection_job(db, household_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projection job not found")
    return read_projection_job(job)
