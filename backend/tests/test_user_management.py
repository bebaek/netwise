def test_user_can_own_and_switch_households(client):
    alice = client.post("/users", json={"display_name": "Alice", "email": "ALICE@example.com"})
    assert alice.status_code == 201
    alice_data = alice.json()
    assert alice_data["email"] == "alice@example.com"

    bob = client.post("/users", json={"display_name": "Bob"})
    assert bob.status_code == 201
    bob_data = bob.json()

    alice_household = client.post(
        "/households",
        json={"name": "Alice Home", "owner_user_id": alice_data["id"]},
    )
    assert alice_household.status_code == 201
    alice_household_data = alice_household.json()

    bob_household = client.post(
        "/households",
        json={"name": "Bob Home", "owner_user_id": bob_data["id"]},
    )
    assert bob_household.status_code == 201
    bob_household_data = bob_household.json()

    alice_households = client.get(f"/households?user_id={alice_data['id']}")
    assert alice_households.status_code == 200
    assert [household["name"] for household in alice_households.json()] == ["Alice Home"]

    bob_households = client.get(f"/users/{bob_data['id']}/households")
    assert bob_households.status_code == 200
    assert [household["name"] for household in bob_households.json()] == ["Bob Home"]

    add_member = client.post(
        f"/households/{alice_household_data['id']}/members",
        json={"user_id": bob_data["id"], "role": "member"},
    )
    assert add_member.status_code == 201
    assert add_member.json()["role"] == "member"

    bob_households = client.get(f"/households?user_id={bob_data['id']}")
    assert bob_households.status_code == 200
    assert {household["name"] for household in bob_households.json()} == {"Alice Home", "Bob Home"}

    members = client.get(f"/households/{alice_household_data['id']}/members")
    assert members.status_code == 200
    assert {member["user"]["display_name"] for member in members.json()} == {"Alice", "Bob"}

    remove_member = client.delete(f"/households/{alice_household_data['id']}/members/{bob_data['id']}")
    assert remove_member.status_code == 204

    bob_households = client.get(f"/households?user_id={bob_data['id']}")
    assert [household["id"] for household in bob_households.json()] == [bob_household_data["id"]]


def test_rejects_duplicate_user_email_and_duplicate_membership(client):
    first = client.post("/users", json={"display_name": "First", "email": "user@example.com"})
    assert first.status_code == 201
    duplicate = client.post("/users", json={"display_name": "Second", "email": "USER@example.com"})
    assert duplicate.status_code == 409

    user_id = first.json()["id"]
    household = client.post("/households", json={"name": "Home", "owner_user_id": user_id})
    assert household.status_code == 201

    duplicate_member = client.post(
        f"/households/{household.json()['id']}/members",
        json={"user_id": user_id, "role": "admin"},
    )
    assert duplicate_member.status_code == 409
