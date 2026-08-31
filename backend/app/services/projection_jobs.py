import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.projection_input import ProjectionInput, load_projection_input
from app.analytics.projections import calculate_projection_from_input
from app.db.models import ProjectionJob, ProjectionJobStatus, now_utc
from app.schemas.projection_job import ProjectionJobRead, ProjectionJobRequest

logger = logging.getLogger(__name__)

PROJECTION_ALGORITHM_VERSION = 1
PROJECTION_JOB_RETENTION = timedelta(days=14)


def _canonical_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical_value(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical_value(item) for item in value), key=str)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def projection_input_fingerprint(projection_input: ProjectionInput) -> str:
    # The engine uses today's date when deciding which periods and automatic
    # sale dates are still eligible, so cached results expire naturally each day.
    return _digest({"as_of_date": date.today(), "input": projection_input})


def projection_cache_key(request: ProjectionJobRequest, input_fingerprint: str) -> str:
    return _digest(
        {
            "algorithm_version": PROJECTION_ALGORITHM_VERSION,
            "input_fingerprint": input_fingerprint,
            "request": request.model_dump(mode="json"),
        }
    )


def _load_input(
    db: Session,
    household_id: UUID,
    request: ProjectionJobRequest,
) -> ProjectionInput:
    if request.end_year < request.start_year:
        raise ValueError("end_year must be greater than or equal to start_year")
    return load_projection_input(
        db,
        household_id,
        request.scenario_id,
        start_date=date(request.start_year, 1, 1),
        end_date=date(request.end_year, 12, 31),
    )


def _job_read(job: ProjectionJob, *, cached: bool = False) -> ProjectionJobRead:
    return ProjectionJobRead(
        id=job.id,
        household_id=job.household_id,
        scenario_id=job.scenario_id,
        status=job.status,
        cached=cached,
        result=job.result,
        error_code=job.error_code,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        expires_at=job.expires_at,
    )


def create_projection_job(
    db: Session,
    household_id: UUID,
    request: ProjectionJobRequest,
) -> ProjectionJobRead:
    projection_input = _load_input(db, household_id, request)
    input_fingerprint = projection_input_fingerprint(projection_input)
    cache_key = projection_cache_key(request, input_fingerprint)
    current_time = now_utc()

    completed = db.scalar(
        select(ProjectionJob)
        .where(
            ProjectionJob.cache_key == cache_key,
            ProjectionJob.status == ProjectionJobStatus.completed.value,
            ProjectionJob.expires_at > current_time,
        )
        .order_by(ProjectionJob.completed_at.desc())
        .limit(1)
    )
    if completed is not None:
        return _job_read(completed, cached=True)

    active = db.scalar(
        select(ProjectionJob).where(
            ProjectionJob.cache_key == cache_key,
            ProjectionJob.status.in_(
                [ProjectionJobStatus.queued.value, ProjectionJobStatus.running.value]
            ),
        )
    )
    if active is not None:
        return _job_read(active, cached=True)

    job = ProjectionJob(
        household_id=household_id,
        scenario_id=projection_input.scenario_id,
        cache_key=cache_key,
        input_fingerprint=input_fingerprint,
        algorithm_version=PROJECTION_ALGORITHM_VERSION,
        status=ProjectionJobStatus.queued.value,
        request=request.model_dump(mode="json"),
        queued_at=current_time,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = db.scalar(
            select(ProjectionJob).where(
                ProjectionJob.cache_key == cache_key,
                ProjectionJob.status.in_(
                    [ProjectionJobStatus.queued.value, ProjectionJobStatus.running.value]
                ),
            )
        )
        if active is None:
            raise
        return _job_read(active, cached=True)
    db.refresh(job)
    return _job_read(job)


def get_projection_job(
    db: Session,
    household_id: UUID,
    job_id: UUID,
) -> ProjectionJob | None:
    return db.scalar(
        select(ProjectionJob).where(
            ProjectionJob.id == job_id,
            ProjectionJob.household_id == household_id,
        )
    )


def read_projection_job(job: ProjectionJob) -> ProjectionJobRead:
    return _job_read(job)


def claim_projection_job(db: Session) -> ProjectionJob | None:
    job = db.scalar(
        select(ProjectionJob)
        .where(ProjectionJob.status == ProjectionJobStatus.queued.value)
        .order_by(ProjectionJob.queued_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        db.rollback()
        return None
    current_time = now_utc()
    job.status = ProjectionJobStatus.running.value
    job.started_at = current_time
    job.heartbeat_at = current_time
    db.commit()
    db.refresh(job)
    return job


def execute_projection_job(
    session_factory: sessionmaker[Session],
    job_id: UUID,
) -> None:
    with session_factory() as db:
        job = db.get(ProjectionJob, job_id)
        if job is None or job.status != ProjectionJobStatus.running.value:
            return
        request = ProjectionJobRequest.model_validate(job.request)
        projection_input = _load_input(db, job.household_id, request)
        current_fingerprint = projection_input_fingerprint(projection_input)
        expected_fingerprint = job.input_fingerprint
        db.rollback()

    if current_fingerprint != expected_fingerprint:
        with session_factory() as db:
            job = db.get(ProjectionJob, job_id)
            if job is not None and job.status == ProjectionJobStatus.running.value:
                job.status = ProjectionJobStatus.stale.value
                job.error_code = "projection_inputs_changed"
                job.completed_at = now_utc()
                job.expires_at = now_utc() + PROJECTION_JOB_RETENTION
                db.commit()
        return

    try:
        result = calculate_projection_from_input(
            projection_input,
            start_year=request.start_year,
            end_year=request.end_year,
            annual_spending=request.annual_spending,
            spending_inflation_rate=request.spending_inflation_rate,
            spending_account_id=request.spending_account_id,
            tax_account_id=request.tax_account_id,
            interval=request.interval,
        )
        encoded_result = jsonable_encoder(result)
    except Exception:
        logger.exception("Projection job %s failed", job_id)
        with session_factory() as db:
            job = db.get(ProjectionJob, job_id)
            if job is not None and job.status == ProjectionJobStatus.running.value:
                job.status = ProjectionJobStatus.failed.value
                job.error_code = "projection_failed"
                job.completed_at = now_utc()
                job.expires_at = now_utc() + PROJECTION_JOB_RETENTION
                db.commit()
        return

    with session_factory() as db:
        job = db.get(ProjectionJob, job_id)
        if job is not None and job.status == ProjectionJobStatus.running.value:
            completed_at = now_utc()
            job.status = ProjectionJobStatus.completed.value
            job.result = encoded_result
            job.completed_at = completed_at
            job.heartbeat_at = completed_at
            job.expires_at = completed_at + PROJECTION_JOB_RETENTION
            db.commit()


def delete_expired_projection_jobs(db: Session) -> int:
    result = db.execute(
        delete(ProjectionJob).where(
            ProjectionJob.expires_at < now_utc(),
            ProjectionJob.status.in_(
                [
                    ProjectionJobStatus.completed.value,
                    ProjectionJobStatus.failed.value,
                    ProjectionJobStatus.stale.value,
                ]
            ),
        )
    )
    db.commit()
    return result.rowcount or 0


def recover_stale_projection_jobs(db: Session, *, older_than: timedelta) -> int:
    cutoff = datetime.now(UTC) - older_than
    jobs = list(
        db.scalars(
            select(ProjectionJob).where(
                ProjectionJob.status == ProjectionJobStatus.running.value,
                ProjectionJob.heartbeat_at < cutoff,
            )
        ).all()
    )
    for job in jobs:
        job.status = ProjectionJobStatus.queued.value
        job.started_at = None
        job.heartbeat_at = None
    if jobs:
        db.commit()
    return len(jobs)
