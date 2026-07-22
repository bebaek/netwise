def test_authenticated_user_owns_households_and_manages_members(client, auth_user):
    alice = client.post("/users", json={"display_name": "Alice", "email": "ALICE@example.com"})
    assert alice.status_code == 201
    assert alice.json()["email"] == "alice@example.com"

    bob = client.post("/users", json={"display_name": "Bob"})
    assert bob.status_code == 201
    bob_data = bob.json()

    first_household = client.post(
        "/households",
        json={"name": "First Home", "owner_user_id": str(auth_user.id)},
    )
    assert first_household.status_code == 201
    first_household_data = first_household.json()

    second_household = client.post("/households", json={"name": "Second Home"})
    assert second_household.status_code == 201

    current_user_households = client.get(f"/households?user_id={auth_user.id}")
    assert current_user_households.status_code == 200
    assert [household["name"] for household in current_user_households.json()] == [
        "First Home",
        "Second Home",
    ]

    other_user_households = client.get(f"/users/{bob_data['id']}/households")
    assert other_user_households.status_code == 403

    add_member = client.post(
        f"/households/{first_household_data['id']}/members",
        json={"user_id": bob_data["id"], "role": "member"},
    )
    assert add_member.status_code == 201
    assert add_member.json()["role"] == "member"

    members = client.get(f"/households/{first_household_data['id']}/members")
    assert members.status_code == 200
    assert {member["user"]["display_name"] for member in members.json()} == {"Test User", "Bob"}

    remove_member = client.delete(
        f"/households/{first_household_data['id']}/members/{bob_data['id']}"
    )
    assert remove_member.status_code == 204

    members = client.get(f"/households/{first_household_data['id']}/members")
    assert [member["user"]["display_name"] for member in members.json()] == ["Test User"]


def test_rejects_duplicate_user_email_and_duplicate_membership(client, auth_user):
    first = client.post("/users", json={"display_name": "First", "email": "user@example.com"})
    assert first.status_code == 201
    duplicate = client.post("/users", json={"display_name": "Second", "email": "USER@example.com"})
    assert duplicate.status_code == 409

    user_id = first.json()["id"]
    household = client.post(
        "/households",
        json={"name": "Home", "owner_user_id": str(auth_user.id)},
    )
    assert household.status_code == 201

    add_member = client.post(
        f"/households/{household.json()['id']}/members",
        json={"user_id": user_id, "role": "member"},
    )
    assert add_member.status_code == 201

    duplicate_member = client.post(
        f"/households/{household.json()['id']}/members",
        json={"user_id": user_id, "role": "admin"},
    )
    assert duplicate_member.status_code == 409
