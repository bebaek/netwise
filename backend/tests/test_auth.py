from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import session_token_digest
from app.db.models import Household, HouseholdMembership, User, UserSession


def test_initial_setup_registers_owner_and_authenticates(unauthenticated_client, db_session):
    status_response = unauthenticated_client.get("/auth/status")
    assert status_response.status_code == 200
    assert status_response.json() == {
        "setup_required": True,
        "public_signup_enabled": False,
        "user": None,
    }

    protected_response = unauthenticated_client.get("/users")
    assert protected_response.status_code == 401

    register_response = unauthenticated_client.post(
        "/auth/register",
        json={
            "display_name": "Alice",
            "email": "ALICE@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == "alice@example.com"
    assert "netwise_session" in register_response.cookies
    set_cookie = register_response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    authenticated_status = unauthenticated_client.get("/auth/status")
    assert authenticated_status.status_code == 200
    assert authenticated_status.json()["setup_required"] is False
    assert authenticated_status.json()["user"]["display_name"] == "Alice"

    users_response = unauthenticated_client.get("/users")
    assert users_response.status_code == 200
    assert [user["display_name"] for user in users_response.json()] == ["Alice"]

    household = db_session.scalar(select(Household))
    user = db_session.scalar(select(User).where(User.email == "alice@example.com"))
    membership = db_session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household.id,
            HouseholdMembership.user_id == user.id,
        )
    )
    assert household.name == "Home"
    assert membership.role == "owner"
    assert user.password_hash != "correct horse battery staple"


def test_login_rejects_bad_password_and_logout_revokes_session(unauthenticated_client, db_session):
    credentials = {
        "display_name": "Alice",
        "email": "alice@example.com",
        "password": "correct horse battery staple",
    }
    assert unauthenticated_client.post("/auth/register", json=credentials).status_code == 201
    assert unauthenticated_client.post("/auth/logout").status_code == 204
    assert db_session.scalar(select(UserSession)) is None

    bad_login = unauthenticated_client.post(
        "/auth/login",
        json={"email": credentials["email"], "password": "this is not the password"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["detail"] == "Invalid email or password"

    login = unauthenticated_client.post(
        "/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert login.status_code == 200
    assert unauthenticated_client.get("/users").status_code == 200

    logout = unauthenticated_client.post("/auth/logout")
    assert logout.status_code == 204
    assert unauthenticated_client.get("/users").status_code == 401


def test_public_registration_is_disabled_after_initial_setup(unauthenticated_client):
    first_registration = unauthenticated_client.post(
        "/auth/register",
        json={
            "display_name": "Alice",
            "email": "alice@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert first_registration.status_code == 201

    second_registration = unauthenticated_client.post(
        "/auth/register",
        json={
            "display_name": "Bob",
            "email": "bob@example.com",
            "password": "another correct horse password",
        },
    )
    assert second_registration.status_code == 403
    assert second_registration.json()["detail"] == "Public signup is disabled"


def test_expired_session_is_rejected_and_removed(unauthenticated_client, db_session):
    user = User(
        display_name="Alice",
        email="alice@example.com",
        password_hash="not-used-by-session-authentication",
    )
    db_session.add(user)
    db_session.flush()
    token = "expired-session-token"
    db_session.add(
        UserSession(
            user_id=user.id,
            token_digest=session_token_digest(token),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    db_session.commit()
    unauthenticated_client.cookies.set("netwise_session", token)

    response = unauthenticated_client.get("/users")

    assert response.status_code == 401
    assert db_session.scalar(select(UserSession)) is None


def test_registration_validates_password_and_email(unauthenticated_client):
    short_password = unauthenticated_client.post(
        "/auth/register",
        json={"display_name": "Alice", "email": "alice@example.com", "password": "too-short"},
    )
    assert short_password.status_code == 422

    invalid_email = unauthenticated_client.post(
        "/auth/register",
        json={
            "display_name": "Alice",
            "email": "not-an-email",
            "password": "correct horse battery staple",
        },
    )
    assert invalid_email.status_code == 422
