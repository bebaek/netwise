from fastapi.testclient import TestClient


def test_health(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_accounts_snapshots_and_net_worth(client: TestClient):
    household = client.post("/households", json={"name": "Home"}).json()
    household_id = household["id"]

    home = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Primary Residence",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "real_estate",
            "currency": "USD",
        },
    ).json()
    mortgage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Primary Mortgage",
            "account_kind": "liability",
            "category": "mortgage",
            "liquidity_class": "liability",
            "currency": "USD",
        },
    ).json()

    assert client.post(
        f"/accounts/{home['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "700000.00"},
    ).status_code == 201
    assert client.post(
        f"/accounts/{mortgage['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "450000.00"},
    ).status_code == 201

    response = client.get(f"/dashboard/{household_id}/net-worth")

    assert response.status_code == 200
    payload = response.json()
    assert payload["assets_total"] == "700000.00"
    assert payload["liabilities_total"] == "450000.00"
    assert payload["net_worth"] == "250000.00"
    assert len(payload["accounts"]) == 2

    event_response = client.post(
        f"/accounts/{home['id']}/events",
        json={
            "event_date": "2026-02-01",
            "amount": "10000.00",
            "event_type": "large_purchase",
            "description": "Kitchen renovation",
            "projection_behavior": "historical_only",
        },
    )
    assert event_response.status_code == 201
    event = event_response.json()
    assert event["household_id"] == household_id
    assert event["account_id"] == home["id"]
    assert event["amount"] == "10000.00"
    assert event["event_type"] == "large_purchase"

    events_response = client.get(f"/accounts/{home['id']}/events")
    assert events_response.status_code == 200
    assert len(events_response.json()) == 1
