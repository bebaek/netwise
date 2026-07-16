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

    property_response = client.post(
        "/real-estate/properties",
        json={
            "account_id": home["id"],
            "property_type": "primary_residence",
            "purchase_date": "2020-01-01",
            "purchase_price": "600000.00",
            "down_payment": "120000.00",
            "expected_appreciation_rate": "0.030000",
            "property_tax_annual": "8000.00",
            "insurance_annual": "1500.00",
            "maintenance_rate": "0.010000",
            "hoa_monthly": "0.00",
        },
    )
    assert property_response.status_code == 201
    property_payload = property_response.json()
    assert property_payload["household_id"] == household_id
    assert property_payload["account_id"] == home["id"]
    assert property_payload["purchase_price"] == "600000.00"

    mortgage_response = client.post(
        "/mortgages",
        json={
            "liability_account_id": mortgage["id"],
            "property_account_id": home["id"],
            "original_principal": "480000.00",
            "interest_rate": "0.045000",
            "term_months": 360,
            "start_date": "2020-01-01",
            "monthly_payment": "2432.00",
            "rate_type": "fixed",
        },
    )
    assert mortgage_response.status_code == 201
    mortgage_payload = mortgage_response.json()
    assert mortgage_payload["household_id"] == household_id
    assert mortgage_payload["liability_account_id"] == mortgage["id"]
    assert mortgage_payload["property_account_id"] == home["id"]

    properties_response = client.get(f"/real-estate/properties?household_id={household_id}")
    assert properties_response.status_code == 200
    assert len(properties_response.json()) == 1

    mortgages_response = client.get(f"/mortgages?household_id={household_id}")
    assert mortgages_response.status_code == 200
    assert len(mortgages_response.json()) == 1
