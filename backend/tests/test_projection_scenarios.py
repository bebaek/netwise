from uuid import UUID

from sqlalchemy import select

from app.db.models import Household, ProjectionScenario
from app.services.projection_scenarios import ensure_baseline_scenario


def _create_household(client, name: str = "Scenario Household") -> dict:
    response = client.post("/households", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_new_household_receives_one_idempotent_baseline(client, db_session):
    household_data = _create_household(client)
    household_id = UUID(household_data["id"])

    response = client.get(f"/households/{household_id}/projection-scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Baseline"
    assert scenarios[0]["is_baseline"] is True
    assert scenarios[0]["created_from_scenario_id"] is None

    household = db_session.get(Household, household_id)
    first = ensure_baseline_scenario(db_session, household)
    second = ensure_baseline_scenario(db_session, household)
    db_session.commit()

    assert first.id == second.id == UUID(scenarios[0]["id"])
    assert len(
        db_session.scalars(
            select(ProjectionScenario).where(ProjectionScenario.household_id == household_id)
        ).all()
    ) == 1


def test_projection_scenario_crud_and_baseline_protection(client):
    household = _create_household(client)
    household_id = household["id"]
    baseline = client.get(f"/households/{household_id}/projection-scenarios").json()[0]

    create_response = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "  Retire early  ", "description": "  Stop work in 2032  "},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Retire early"
    assert created["description"] == "Stop work in 2032"
    assert created["is_baseline"] is False

    get_response = client.get(f"/projection-scenarios/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["household_id"] == household_id

    patch_response = client.patch(
        f"/projection-scenarios/{created['id']}",
        json={"name": "Later retirement", "description": None},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Later retirement"
    assert patch_response.json()["description"] is None

    duplicate_name = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "Later retirement"},
    )
    assert duplicate_name.status_code == 409

    delete_baseline = client.delete(f"/projection-scenarios/{baseline['id']}")
    assert delete_baseline.status_code == 409

    rename_baseline = client.patch(
        f"/projection-scenarios/{baseline['id']}",
        json={"name": "Current plan"},
    )
    assert rename_baseline.status_code == 200
    assert rename_baseline.json()["is_baseline"] is True

    delete_response = client.delete(f"/projection-scenarios/{created['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/projection-scenarios/{created['id']}").status_code == 404

    remaining = client.get(f"/households/{household_id}/projection-scenarios").json()
    assert [(item["name"], item["is_baseline"]) for item in remaining] == [
        ("Current plan", True)
    ]


def test_projection_scenario_rejects_invalid_names_and_enforces_limit(client):
    household_id = _create_household(client)["id"]

    empty_name = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "   "},
    )
    assert empty_name.status_code == 400

    for index in range(1, 20):
        response = client.post(
            f"/households/{household_id}/projection-scenarios",
            json={"name": f"Scenario {index}"},
        )
        assert response.status_code == 201

    over_limit = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "One too many"},
    )
    assert over_limit.status_code == 409
    assert "at most 20" in over_limit.json()["detail"]
