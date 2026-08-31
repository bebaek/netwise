from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ProjectionJob, ProjectionJobStatus
from app.schemas.projection_job import ProjectionJobRequest
from app.services.projection_jobs import (
    claim_projection_job,
    execute_projection_job,
    projection_cache_key,
)


def _request() -> dict:
    return {
        "start_year": 2026,
        "end_year": 2027,
        "interval": "quarterly",
    }


def test_projection_job_runs_and_reuses_completed_result(
    client: TestClient,
    db_session: Session,
) -> None:
    household_id = client.post("/households", json={"name": "Async Projection"}).json()["id"]
    client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Cash",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    )

    created = client.post(f"/dashboard/{household_id}/projection-jobs", json=_request())

    assert created.status_code == 202
    assert created.json()["status"] == "queued"
    assert created.json()["cached"] is False
    job_id = UUID(created.json()["id"])

    job = claim_projection_job(db_session)
    assert job is not None
    assert job.id == job_id
    assert job.status == ProjectionJobStatus.running.value

    worker_sessions = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
    )
    execute_projection_job(worker_sessions, job_id)
    db_session.expire_all()

    completed = client.get(f"/dashboard/{household_id}/projection-jobs/{job_id}")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["result"]["interval"] == "quarterly"
    assert completed.json()["result"]["start_year"] == 2026
    assert completed.json()["result"]["end_year"] == 2027

    cached = client.post(f"/dashboard/{household_id}/projection-jobs", json=_request())
    assert cached.status_code == 202
    assert cached.json()["id"] == str(job_id)
    assert cached.json()["status"] == "completed"
    assert cached.json()["cached"] is True


def test_projection_job_is_marked_stale_when_inputs_change(
    client: TestClient,
    db_session: Session,
) -> None:
    household_id = client.post("/households", json={"name": "Changing Projection"}).json()["id"]
    created = client.post(f"/dashboard/{household_id}/projection-jobs", json=_request())
    job_id = UUID(created.json()["id"])
    assert claim_projection_job(db_session) is not None

    client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "New Cash",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    )

    worker_sessions = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
    )
    execute_projection_job(worker_sessions, job_id)
    db_session.expire_all()

    response = client.get(f"/dashboard/{household_id}/projection-jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "stale"
    assert response.json()["error_code"] == "projection_inputs_changed"


def test_projection_job_status_is_scoped_to_household(client: TestClient) -> None:
    first = client.post("/households", json={"name": "First"}).json()["id"]
    second = client.post("/households", json={"name": "Second"}).json()["id"]
    created = client.post(f"/dashboard/{first}/projection-jobs", json=_request())

    response = client.get(f"/dashboard/{second}/projection-jobs/{created.json()['id']}")

    assert response.status_code == 404


def test_projection_job_rejects_invalid_year_range(client: TestClient) -> None:
    household_id = client.post("/households", json={"name": "Invalid"}).json()["id"]

    response = client.post(
        f"/dashboard/{household_id}/projection-jobs",
        json={"start_year": 2030, "end_year": 2026},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "end_year must be greater than or equal to start_year"


def test_projection_cache_key_normalizes_decimal_values() -> None:
    first = ProjectionJobRequest(
        start_year=2026,
        end_year=2030,
        annual_spending="100.00",
    )
    second = ProjectionJobRequest(
        start_year=2026,
        end_year=2030,
        annual_spending="100.00",
    )

    assert projection_cache_key(first, "fingerprint") == projection_cache_key(
        second, "fingerprint"
    )


def test_claim_returns_oldest_queued_job(client: TestClient, db_session: Session) -> None:
    household_id = client.post("/households", json={"name": "Queue"}).json()["id"]
    first = client.post(
        f"/dashboard/{household_id}/projection-jobs",
        json={"start_year": 2026, "end_year": 2026},
    ).json()
    second = client.post(
        f"/dashboard/{household_id}/projection-jobs",
        json={"start_year": 2026, "end_year": 2027},
    ).json()

    claimed = claim_projection_job(db_session)

    assert claimed is not None
    assert str(claimed.id) == first["id"]
    assert db_session.get(ProjectionJob, UUID(second["id"])).status == "queued"
