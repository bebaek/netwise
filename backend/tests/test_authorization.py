from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.security import create_user_session
from app.db.models import HouseholdMembership, User


def _register_initial_owner(client) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "display_name": "Owner",
            "email": "owner@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    return response.json()


def _use_session(client, db, user: User) -> None:
    _, token = create_user_session(db, user, Settings(enable_admin_tools=True))
    db.commit()
    client.cookies.set("netwise_session", token)


def _create_user(db, name: str) -> User:
    user = User(id=uuid4(), display_name=name, email=f"{name.lower()}@example.com")
    db.add(user)
    db.commit()
    return user


def _add_membership(db, household_id: str, user: User, role: str) -> None:
    db.add(HouseholdMembership(household_id=UUID(household_id), user_id=user.id, role=role))
    db.commit()


def _account_payload(household_id: str, name: str) -> dict:
    return {
        "household_id": household_id,
        "name": name,
        "account_kind": "asset",
        "category": "cash",
        "liquidity_class": "cash",
        "currency": "USD",
    }


def test_non_member_cannot_discover_household_or_resources(unauthenticated_client, db_session):
    owner = _register_initial_owner(unauthenticated_client)
    households = unauthenticated_client.get("/households").json()
    household_id = households[0]["id"]
    account = unauthenticated_client.post(
        "/accounts", json=_account_payload(household_id, "Owner Cash")
    ).json()

    outsider = _create_user(db_session, "Outsider")
    _use_session(unauthenticated_client, db_session, outsider)
    outsider_household = unauthenticated_client.post(
        "/households", json={"name": "Outsider Home"}
    ).json()

    assert [item["name"] for item in unauthenticated_client.get("/households").json()] == [
        "Outsider Home"
    ]
    assert unauthenticated_client.get(f"/households?user_id={owner['id']}").status_code == 403
    assert unauthenticated_client.get(f"/households/{household_id}").status_code == 404
    assert unauthenticated_client.get(f"/households/{household_id}/events").status_code == 404
    assert unauthenticated_client.get(f"/dashboard/{household_id}/net-worth").status_code == 404
    assert unauthenticated_client.get(f"/accounts/{account['id']}").status_code == 404
    visible_users = unauthenticated_client.get("/users")
    assert [user["display_name"] for user in visible_users.json()] == ["Outsider"]
    assert unauthenticated_client.get(f"/users/{owner['id']}").status_code == 404
    confused_deputy_attempt = unauthenticated_client.post(
        f"/accounts?household_id={outsider_household['id']}",
        json=_account_payload(household_id, "Stolen Access"),
    )
    assert confused_deputy_attempt.status_code == 404
    assert unauthenticated_client.get(f"/users/{owner['id']}/households").status_code == 403


def test_viewer_is_read_only_and_member_can_write(unauthenticated_client, db_session):
    owner_data = _register_initial_owner(unauthenticated_client)
    household_id = unauthenticated_client.get("/households").json()[0]["id"]
    account = unauthenticated_client.post(
        "/accounts", json=_account_payload(household_id, "Owner Cash")
    ).json()

    viewer = _create_user(db_session, "Viewer")
    _add_membership(db_session, household_id, viewer, "viewer")
    _use_session(unauthenticated_client, db_session, viewer)

    assert unauthenticated_client.get(f"/users/{owner_data['id']}").status_code == 200
    assert unauthenticated_client.get(f"/households/{household_id}").status_code == 200
    assert unauthenticated_client.get(f"/accounts?household_id={household_id}").status_code == 200
    assert unauthenticated_client.get(f"/accounts/{account['id']}").status_code == 200
    assert unauthenticated_client.get(f"/households/{household_id}/events").status_code == 200
    assert (
        unauthenticated_client.post(
            "/accounts", json=_account_payload(household_id, "Viewer Cash")
        ).status_code
        == 403
    )
    assert (
        unauthenticated_client.patch(
            f"/accounts/{account['id']}", json={"name": "Changed"}
        ).status_code
        == 403
    )
    assert (
        unauthenticated_client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-07-22", "balance": "100.00"},
        ).status_code
        == 403
    )

    viewer_members = unauthenticated_client.get(f"/households/{household_id}/members")
    assert viewer_members.status_code == 200

    member = _create_user(db_session, "Member")
    _add_membership(db_session, household_id, member, "member")
    _use_session(unauthenticated_client, db_session, member)
    create_response = unauthenticated_client.post(
        "/accounts", json=_account_payload(household_id, "Member Cash")
    )
    assert create_response.status_code == 201
    assert (
        unauthenticated_client.post(
            f"/households/{household_id}/members",
            json={"user_id": str(uuid4()), "role": "viewer"},
        ).status_code
        == 403
    )


def test_owner_and_admin_membership_boundaries(unauthenticated_client, db_session):
    owner_data = _register_initial_owner(unauthenticated_client)
    household_id = unauthenticated_client.get("/households").json()[0]["id"]
    owner = db_session.get(User, UUID(owner_data["id"]))

    cannot_remove_last_owner = unauthenticated_client.delete(
        f"/households/{household_id}/members/{owner.id}"
    )
    assert cannot_remove_last_owner.status_code == 409

    admin = _create_user(db_session, "Admin")
    _add_membership(db_session, household_id, admin, "admin")
    candidate_owner = _create_user(db_session, "Candidate")
    _use_session(unauthenticated_client, db_session, admin)

    grant_owner = unauthenticated_client.post(
        f"/households/{household_id}/members",
        json={"user_id": str(candidate_owner.id), "role": "owner"},
    )
    assert grant_owner.status_code == 403

    remove_owner = unauthenticated_client.delete(
        f"/households/{household_id}/members/{owner.id}"
    )
    assert remove_owner.status_code == 403

    add_viewer = _create_user(db_session, "NewViewer")
    add_response = unauthenticated_client.post(
        f"/households/{household_id}/members",
        json={"user_id": str(add_viewer.id), "role": "viewer"},
    )
    assert add_response.status_code == 201

    export_response = unauthenticated_client.get(f"/households/{household_id}/export")
    assert export_response.status_code == 200


def test_projection_scenario_authorization_boundaries(unauthenticated_client, db_session):
    _register_initial_owner(unauthenticated_client)
    household_id = unauthenticated_client.get("/households").json()[0]["id"]
    baseline = unauthenticated_client.get(
        f"/households/{household_id}/projection-scenarios"
    ).json()[0]
    account = unauthenticated_client.post(
        "/accounts", json=_account_payload(household_id, "Scenario Cash")
    ).json()
    comparison_scenario = unauthenticated_client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "Comparison scenario"},
    ).json()

    viewer = _create_user(db_session, "ScenarioViewer")
    _add_membership(db_session, household_id, viewer, "viewer")
    _use_session(unauthenticated_client, db_session, viewer)

    assert (
        unauthenticated_client.get(
            f"/households/{household_id}/projection-scenarios"
        ).status_code
        == 200
    )
    assert (
        unauthenticated_client.get(
            f"/projection-scenarios/{baseline['id']}/account-assumptions"
        ).status_code
        == 200
    )
    assert (
        unauthenticated_client.put(
            f"/projection-scenarios/{baseline['id']}/account-assumptions/{account['id']}",
            json={"expected_annual_yield": "0.010000"},
        ).status_code
        == 403
    )
    assert (
        unauthenticated_client.get(f"/projection-scenarios/{baseline['id']}").status_code
        == 200
    )
    viewer_comparison = unauthenticated_client.post(
        f"/dashboard/{household_id}/projection-comparison",
        json={
            "scenario_ids": [baseline["id"], comparison_scenario["id"]],
            "start_year": 2026,
            "end_year": 2027,
            "interval": "annual",
        },
    )
    assert viewer_comparison.status_code == 200
    viewer_household = unauthenticated_client.post(
        "/households", json={"name": "Viewer-owned comparison household"}
    ).json()
    viewer_household_baseline = unauthenticated_client.get(
        f"/households/{viewer_household['id']}/projection-scenarios"
    ).json()[0]
    viewer_household_baseline = unauthenticated_client.patch(
        f"/projection-scenarios/{viewer_household_baseline['id']}",
        json={"name": "Private comparison plan"},
    ).json()
    cross_household_comparison = unauthenticated_client.post(
        f"/dashboard/{household_id}/projection-comparison",
        json={
            "scenario_ids": [baseline["id"], viewer_household_baseline["id"]],
            "start_year": 2026,
            "end_year": 2027,
            "interval": "annual",
        },
    )
    assert cross_household_comparison.status_code == 400
    assert cross_household_comparison.json()["detail"] == "Projection scenario not found"
    assert viewer_household_baseline["name"] not in cross_household_comparison.text
    assert (
        unauthenticated_client.post(
            f"/households/{household_id}/projection-scenarios",
            json={"name": "Viewer scenario"},
        ).status_code
        == 403
    )
    assert (
        unauthenticated_client.post(
            f"/projection-scenarios/{baseline['id']}/duplicate",
            json={"name": "Viewer duplicate"},
        ).status_code
        == 403
    )
    assert (
        unauthenticated_client.patch(
            f"/projection-scenarios/{baseline['id']}",
            json={"name": "Viewer rename"},
        ).status_code
        == 403
    )
    assert (
        unauthenticated_client.delete(
            f"/projection-scenarios/{baseline['id']}"
        ).status_code
        == 403
    )

    member = _create_user(db_session, "ScenarioMember")
    _add_membership(db_session, household_id, member, "member")
    _use_session(unauthenticated_client, db_session, member)
    create_response = unauthenticated_client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "Member scenario"},
    )
    assert create_response.status_code == 201
    duplicate_response = unauthenticated_client.post(
        f"/projection-scenarios/{baseline['id']}/duplicate",
        json={"name": "Member duplicate"},
    )
    assert duplicate_response.status_code == 201
    update_assumption = unauthenticated_client.put(
        f"/projection-scenarios/{baseline['id']}/account-assumptions/{account['id']}",
        json={"expected_annual_yield": "0.010000"},
    )
    assert update_assumption.status_code == 200

    outsider = _create_user(db_session, "ScenarioOutsider")
    _use_session(unauthenticated_client, db_session, outsider)
    assert (
        unauthenticated_client.get(
            f"/projection-scenarios/{baseline['id']}/account-assumptions"
        ).status_code
        == 404
    )
    assert (
        unauthenticated_client.post(
            f"/projection-scenarios/{baseline['id']}/duplicate",
            json={"name": "Outsider duplicate"},
        ).status_code
        == 404
    )
    assert (
        unauthenticated_client.get(f"/projection-scenarios/{baseline['id']}").status_code
        == 404
    )
    assert (
        unauthenticated_client.get(
            f"/households/{household_id}/projection-scenarios"
        ).status_code
        == 404
    )
    assert (
        unauthenticated_client.post(
            f"/dashboard/{household_id}/projection-comparison",
            json={
                "scenario_ids": [baseline["id"], comparison_scenario["id"]],
                "start_year": 2026,
                "end_year": 2027,
                "interval": "annual",
            },
        ).status_code
        == 404
    )


def test_new_household_is_owned_by_authenticated_user(unauthenticated_client, db_session):
    _register_initial_owner(unauthenticated_client)
    second_user = _create_user(db_session, "Second")
    _use_session(unauthenticated_client, db_session, second_user)

    response = unauthenticated_client.post("/households", json={"name": "Second Home"})
    assert response.status_code == 201
    household_id = response.json()["id"]

    memberships = (
        db_session.query(HouseholdMembership)
        .filter_by(household_id=UUID(household_id))
        .all()
    )
    assert len(memberships) == 1
    assert memberships[0].user_id == second_user.id
    assert memberships[0].role == "owner"
    assert [item["name"] for item in unauthenticated_client.get("/households").json()] == [
        "Second Home"
    ]
