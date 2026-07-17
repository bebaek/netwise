from fastapi.testclient import TestClient


def test_list_update_and_delete_snapshots(client: TestClient):
    household = client.post("/households", json={"name": "Snapshot Management"}).json()
    account = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Checking",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "currency": "USD",
        },
    ).json()

    first = client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "1000.00"},
    ).json()
    second = client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-02-01", "balance": "1200.00"},
    ).json()

    list_response = client.get(f"/households/{household['id']}/snapshots")
    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": second["id"],
            "household_id": household["id"],
            "account_id": account["id"],
            "account_name": "Checking",
            "account_kind": "asset",
            "account_category": "cash",
            "as_of_date": "2026-02-01",
            "balance": "1200.00",
            "currency": "USD",
            "source": "manual",
            "confidence_level": None,
            "created_at": second["created_at"],
        },
        {
            "id": first["id"],
            "household_id": household["id"],
            "account_id": account["id"],
            "account_name": "Checking",
            "account_kind": "asset",
            "account_category": "cash",
            "as_of_date": "2026-01-01",
            "balance": "1000.00",
            "currency": "USD",
            "source": "manual",
            "confidence_level": None,
            "created_at": first["created_at"],
        },
    ]

    update_response = client.patch(
        f"/accounts/{account['id']}/snapshots/{first['id']}",
        json={"as_of_date": "2026-01-15", "balance": "1100.00"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["as_of_date"] == "2026-01-15"
    assert update_response.json()["balance"] == "1100.00"

    conflict_response = client.patch(
        f"/accounts/{account['id']}/snapshots/{first['id']}",
        json={"as_of_date": "2026-02-01"},
    )
    assert conflict_response.status_code == 409

    delete_response = client.delete(f"/accounts/{account['id']}/snapshots/{second['id']}")
    assert delete_response.status_code == 204

    list_response = client.get(f"/households/{household['id']}/snapshots")
    assert list_response.status_code == 200
    assert [snapshot["id"] for snapshot in list_response.json()] == [first["id"]]
