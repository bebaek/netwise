from fastapi.testclient import TestClient


def test_projection_uses_account_yields_and_projection_events(client: TestClient):
    household = client.post("/households", json={"name": "Projection Home"}).json()
    household_id = household["id"]

    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.100000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{brokerage['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "100000.00"},
    )
    client.post(
        f"/accounts/{brokerage['id']}/events",
        json={
            "event_date": "2026-06-01",
            "amount": "5000.00",
            "event_type": "contribution",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2027"
    )

    assert response.status_code == 200
    projection = response.json()
    assert projection["start_year"] == 2026
    assert projection["end_year"] == 2027
    assert projection["points"][0]["net_worth"] == "115000.00"
    assert projection["points"][1]["net_worth"] == "126500.00"


def test_projection_projects_real_estate_and_mortgage_balance(client: TestClient):
    household = client.post("/households", json={"name": "Mortgage Projection"}).json()
    household_id = household["id"]

    home = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Home",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "illiquid",
            "currency": "USD",
        },
    ).json()
    mortgage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Mortgage",
            "account_kind": "liability",
            "category": "mortgage",
            "liquidity_class": "debt",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{home['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "500000.00"},
    )
    client.post(
        f"/accounts/{mortgage['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "300000.00"},
    )
    client.post(
        "/real-estate/properties",
        json={
            "account_id": home["id"],
            "property_type": "residence",
            "expected_appreciation_rate": "0.040000",
        },
    )
    client.post(
        "/mortgages",
        json={
            "liability_account_id": mortgage["id"],
            "property_account_id": home["id"],
            "original_principal": "300000.00",
            "interest_rate": "0.000000",
            "term_months": 360,
            "start_date": "2026-01-01",
            "rate_type": "fixed",
        },
    )

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026"
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["assets_total"] == "520000.00"
    assert point["liabilities_total"] == "290833.33"
    assert point["net_worth"] == "229166.67"


def test_projection_rejects_invalid_year_range(client: TestClient):
    household = client.post("/households", json={"name": "Invalid Projection"}).json()

    response = client.get(
        f"/dashboard/{household['id']}/projection?start_year=2030&end_year=2026"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "end_year must be greater than or equal to start_year"
