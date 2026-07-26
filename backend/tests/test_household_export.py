from fastapi.testclient import TestClient


def test_household_export_includes_portable_household_data(client: TestClient, auth_user):
    household = client.post(
        "/households",
        json={"name": "Export Home", "owner_user_id": str(auth_user.id)},
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
        "/spending-items",
        json={
            "household_id": household_id,
            "name": "Groceries",
            "category": "food",
            "annual_amount": "9000.00",
            "retirement_annual_amount": "8400.00",
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
    baseline = client.get(f"/households/{household_id}/projection-scenarios").json()[0]
    client.put(
        f"/projection-settings/{household_id}",
        json={"annual_spending": "50000.00", "spending_mode": "manual"},
    )
    duplicate = client.post(
        f"/projection-scenarios/{baseline['id']}/duplicate",
        json={"name": "Exported alternative"},
    ).json()

    response = client.get(f"/households/{household_id}/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "netwise.household_export.v1"
    assert payload["exported_at"]
    assert payload["household"]["id"] == household_id
    assert payload["household"]["name"] == "Export Home"
    assert payload["members"][0]["user"]["email"] == "test@example.com"
    assert payload["accounts"][0]["name"] == "Brokerage"
    assert payload["accounts"][0]["expected_annual_yield"] == "0.060000"
    assert [scenario["id"] for scenario in payload["projection_scenarios"]] == [
        baseline["id"],
        duplicate["id"],
    ]
    assert payload["projection_scenarios"][1]["created_from_scenario_id"] == baseline["id"]
    assert {row["scenario_id"] for row in payload["projection_settings"]} == {
        baseline["id"],
        duplicate["id"],
    }
    assert {row["scenario_id"] for row in payload["income_sources"]} == {
        baseline["id"],
        duplicate["id"],
    }
    assert {row["scenario_id"] for row in payload["spending_items"]} == {
        baseline["id"],
        duplicate["id"],
    }
    assert len(payload["projection_scenario_account_assumptions"]) == 2
    assert payload["snapshots"][0]["balance"] == "1234.56"
    assert payload["account_events"][0]["description"] == "Test contribution"
    assert payload["income_sources"][0]["name"] == "Salary"
    assert payload["spending_items"][0]["name"] == "Groceries"
    assert payload["spending_items"][0]["retirement_annual_amount"] == "8400.00"
    assert payload["annual_tax_records"][0]["tax_year"] == 2026


def test_household_export_returns_404_for_missing_household(client: TestClient):
    response = client.get("/households/00000000-0000-0000-0000-000000000000/export")

    assert response.status_code == 404
