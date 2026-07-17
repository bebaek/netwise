from fastapi.testclient import TestClient


def test_snapshot_batch_creates_and_updates_household_snapshots(client: TestClient):
    household = client.post("/households", json={"name": "Snapshot Home"}).json()
    checking = client.post(
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
    mortgage = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Mortgage",
            "account_kind": "liability",
            "category": "mortgage",
            "liquidity_class": "debt",
            "currency": "USD",
        },
    ).json()

    create_response = client.post(
        f"/households/{household['id']}/snapshot-batch",
        json={
            "as_of_date": "2026-07-17",
            "snapshots": [
                {"account_id": checking["id"], "balance": "25000.00"},
                {"account_id": mortgage["id"], "balance": "400000.00"},
            ],
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["created_count"] == 2
    assert create_payload["updated_count"] == 0
    assert len(create_payload["snapshots"]) == 2

    net_worth_response = client.get(f"/dashboard/{household['id']}/net-worth")
    assert net_worth_response.status_code == 200
    assert net_worth_response.json()["net_worth"] == "-375000.00"

    update_response = client.post(
        f"/households/{household['id']}/snapshot-batch",
        json={
            "as_of_date": "2026-07-17",
            "snapshots": [
                {"account_id": checking["id"], "balance": "30000.00"},
                {"account_id": mortgage["id"], "balance": "395000.00"},
            ],
        },
    )
    assert update_response.status_code == 201
    update_payload = update_response.json()
    assert update_payload["created_count"] == 0
    assert update_payload["updated_count"] == 2

    net_worth_response = client.get(f"/dashboard/{household['id']}/net-worth")
    assert net_worth_response.status_code == 200
    assert net_worth_response.json()["net_worth"] == "-365000.00"


def test_snapshot_batch_rejects_other_household_account(client: TestClient):
    household = client.post("/households", json={"name": "Home"}).json()
    other_household = client.post("/households", json={"name": "Other"}).json()
    other_account = client.post(
        "/accounts",
        json={
            "household_id": other_household["id"],
            "name": "Other checking",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "currency": "USD",
        },
    ).json()

    response = client.post(
        f"/households/{household['id']}/snapshot-batch",
        json={
            "as_of_date": "2026-07-17",
            "snapshots": [{"account_id": other_account["id"], "balance": "100.00"}],
        },
    )

    assert response.status_code == 400
    assert "Accounts do not belong to household" in response.json()["detail"]
