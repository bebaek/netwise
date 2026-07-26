from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import ApiToken, ApiTokenAuditEvent, Household, HouseholdMembership


def _register(client) -> None:
    response = client.post(
        "/auth/register",
        json={
            "display_name": "Agent Owner",
            "email": "agent@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201


def _create_token(client, household_id, scopes=None):
    payload = {
        "name": "My finance agent",
        "household_id": str(household_id),
        "expires_in_days": 30,
    }
    if scopes is not None:
        payload["scopes"] = scopes
    response = client.post("/api-tokens", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_api_token_is_returned_once_and_authenticates_read_requests(
    unauthenticated_client, db_session
):
    _register(unauthenticated_client)
    household = db_session.scalar(select(Household))

    created = _create_token(unauthenticated_client, household.id)
    assert created["token"].startswith("nwt_")
    assert created["token_prefix"] == created["token"][:12]
    assert created["scopes"] == ["finance:read"]

    listed = unauthenticated_client.get("/api-tokens")
    assert listed.status_code == 200
    assert "token" not in listed.json()[0]

    unauthenticated_client.cookies.clear()
    headers = {"Authorization": f"Bearer {created['token']}"}
    response = unauthenticated_client.get(f"/households/{household.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(household.id)
    db_session.expire_all()
    stored = db_session.scalar(select(ApiToken))
    assert stored.token_digest != created["token"]
    assert stored.last_used_at is not None


def test_api_token_is_read_only_and_cannot_access_identity_or_admin_routes(
    unauthenticated_client, db_session
):
    _register(unauthenticated_client)
    household = db_session.scalar(select(Household))
    created = _create_token(unauthenticated_client, household.id, ["finance:read"])
    unauthenticated_client.cookies.clear()
    headers = {"Authorization": f"Bearer {created['token']}"}

    write_response = unauthenticated_client.post(
        "/households", json={"name": "Not allowed"}, headers=headers
    )
    assert write_response.status_code == 403
    assert write_response.json()["detail"] == "API token scope does not permit this action"

    users_response = unauthenticated_client.get("/users", headers=headers)
    assert users_response.status_code == 403
    members_response = unauthenticated_client.get(
        f"/households/{household.id}/members", headers=headers
    )
    assert members_response.status_code == 403


def test_api_token_is_limited_to_its_household(unauthenticated_client, db_session):
    _register(unauthenticated_client)
    households = list(db_session.scalars(select(Household)).all())
    primary = households[0]
    membership = db_session.scalar(select(HouseholdMembership))
    other = Household(name="Other")
    db_session.add(other)
    db_session.flush()
    db_session.add(
        HouseholdMembership(user_id=membership.user_id, household_id=other.id, role="owner")
    )
    db_session.commit()

    created = _create_token(unauthenticated_client, primary.id)
    unauthenticated_client.cookies.clear()
    headers = {"Authorization": f"Bearer {created['token']}"}

    listed = unauthenticated_client.get("/households", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [str(primary.id)]
    denied = unauthenticated_client.get(f"/households/{other.id}", headers=headers)
    assert denied.status_code == 404


def test_revoked_and_expired_api_tokens_are_rejected(unauthenticated_client, db_session):
    _register(unauthenticated_client)
    household = db_session.scalar(select(Household))
    created = _create_token(unauthenticated_client, household.id)

    revoke = unauthenticated_client.delete(f"/api-tokens/{created['id']}")
    assert revoke.status_code == 204
    unauthenticated_client.cookies.clear()
    headers = {"Authorization": f"Bearer {created['token']}"}
    assert unauthenticated_client.get(f"/households/{household.id}", headers=headers).status_code == 401

    token = db_session.scalar(select(ApiToken))
    token.revoked_at = None
    token.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    assert unauthenticated_client.get(f"/households/{household.id}", headers=headers).status_code == 401


def test_api_token_requests_are_audited_without_financial_payloads(
    unauthenticated_client, db_session
):
    _register(unauthenticated_client)
    household = db_session.scalar(select(Household))
    created = _create_token(unauthenticated_client, household.id)
    unauthenticated_client.cookies.clear()
    headers = {
        "Authorization": f"Bearer {created['token']}",
        "X-Netwise-Agent-Tool": "get_financial_summary",
    }

    read_response = unauthenticated_client.get(
        f"/households/{household.id}", headers=headers
    )
    denied_response = unauthenticated_client.post(
        "/households",
        json={"name": "Must not appear in the audit log"},
        headers={**headers, "X-Netwise-Agent-Tool": "attempted_write"},
    )
    assert read_response.status_code == 200
    assert denied_response.status_code == 403

    login = unauthenticated_client.post(
        "/auth/login",
        json={
            "email": "agent@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert login.status_code == 200
    audit_response = unauthenticated_client.get(
        "/api-tokens/audit-events",
        params={"household_id": str(household.id), "limit": 10},
    )

    assert audit_response.status_code == 200
    events = audit_response.json()
    assert [(event["path"], event["status_code"], event["tool_name"]) for event in events] == [
        ("/households", 403, "attempted_write"),
        ("/households/{household_id}", 200, "get_financial_summary"),
    ]
    assert all(event["token_prefix"] == created["token_prefix"] for event in events)
    assert all(created["token"] not in str(event) for event in events)
    assert all("Must not appear" not in str(event) for event in events)
    assert db_session.scalar(select(ApiTokenAuditEvent.id)) is not None
