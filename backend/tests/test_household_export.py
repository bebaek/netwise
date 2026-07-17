from fastapi.testclient import TestClient


def test_household_export_includes_portable_household_data(client: TestClient):
    user = client.post("/users", json={"display_name": "Ada", "email": "ada@example.com"}).json()
    household = client.post(
        "/households",
        json={"name": "Export Home", "owner_user_id": user["id"]},
    ).json()
    household_id = household["id"]

    account = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.060000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "1234.56"},
    )
    client.post(
        f"/accounts/{account['id']}/events",
        json={
            "event_date": "2026-01-02",
            "amount": "100.00",
            "event_type": "contribution",
            "description": "Test contribution",
            "projection_behavior": "historical_and_projection",
        },
    )
    client.post(
        "/income-sources",
        json={
            "household_id": household_id,
            "name": "Salary",
            "income_type": "salary",
            "amount": "120000.00",
            "currency": "USD",
            "frequency": "annually",
            "start_date": "2026-01-01",
        },
    )
    client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2026,
            "gross_income": "120000.00",
            "total_taxes_paid": "30000.00",
        },
    )

    response = client.get(f"/households/{household_id}/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "netwise.household_export.v1"
    assert payload["exported_at"]
    assert payload["household"]["id"] == household_id
    assert payload["household"]["name"] == "Export Home"
    assert payload["members"][0]["user"]["email"] == "ada@example.com"
    assert payload["accounts"][0]["name"] == "Brokerage"
    assert payload["accounts"][0]["expected_annual_yield"] == "0.060000"
    assert payload["snapshots"][0]["balance"] == "1234.56"
    assert payload["account_events"][0]["description"] == "Test contribution"
    assert payload["income_sources"][0]["name"] == "Salary"
    assert payload["annual_tax_records"][0]["tax_year"] == 2026


def test_household_export_returns_404_for_missing_household(client: TestClient):
    response = client.get("/households/00000000-0000-0000-0000-000000000000/export")

    assert response.status_code == 404
