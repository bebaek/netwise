from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import func, select

from app.db.models import (
    AccountEvent,
    ProjectionScenarioAccountAssumption,
    SpendingItem,
)


def _create_household_and_account(client: TestClient) -> tuple[dict, dict]:
    household = client.post("/households", json={"name": "Scenario Isolation"}).json()
    account = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Scenario Cash",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "cash",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    snapshot = client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "100.00"},
    )
    assert snapshot.status_code == 201
    return household, account


def test_scenario_planning_records_and_events_are_isolated(client: TestClient, db_session):
    household, account = _create_household_and_account(client)
    household_id = household["id"]
    baseline = client.get(f"/households/{household_id}/projection-scenarios").json()[0]
    alternative_response = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "Alternative"},
    )
    assert alternative_response.status_code == 201
    alternative = alternative_response.json()

    baseline_spending = client.post(
        "/spending-items",
        json={
            "household_id": household_id,
            "name": "Baseline spending",
            "category": "living",
            "annual_amount": "1000.00",
        },
    )
    alternative_spending = client.post(
        f"/spending-items?scenario_id={alternative['id']}",
        json={
            "household_id": household_id,
            "name": "Alternative spending",
            "category": "living",
            "annual_amount": "2000.00",
        },
    )
    assert baseline_spending.status_code == alternative_spending.status_code == 201
    assert baseline_spending.json()["scenario_id"] == baseline["id"]
    assert alternative_spending.json()["scenario_id"] == alternative["id"]

    baseline_items = client.get(f"/spending-items?household_id={household_id}").json()
    alternative_items = client.get(
        f"/spending-items?household_id={household_id}&scenario_id={alternative['id']}"
    ).json()
    assert [item["name"] for item in baseline_items] == ["Baseline spending"]
    assert [item["name"] for item in alternative_items] == ["Alternative spending"]

    shared_event = client.post(
        f"/accounts/{account['id']}/events",
        json={
            "event_date": "2025-12-01",
            "amount": "10.00",
            "event_type": "contribution",
            "projection_behavior": "historical_and_projection",
        },
    )
    baseline_event = client.post(
        f"/accounts/{account['id']}/events",
        json={
            "event_date": "2027-01-01",
            "amount": "20.00",
            "event_type": "contribution",
            "projection_behavior": "projection_only",
        },
    )
    alternative_event = client.post(
        f"/accounts/{account['id']}/events",
        json={
            "event_date": "2027-01-01",
            "amount": "30.00",
            "event_type": "contribution",
            "projection_behavior": "projection_only",
            "scenario_id": alternative["id"],
        },
    )
    assert shared_event.status_code == baseline_event.status_code == alternative_event.status_code == 201
    assert shared_event.json()["scenario_id"] is None
    assert baseline_event.json()["scenario_id"] == baseline["id"]
    assert alternative_event.json()["scenario_id"] == alternative["id"]

    baseline_events = client.get(f"/accounts/{account['id']}/events").json()
    alternative_events = client.get(
        f"/accounts/{account['id']}/events?scenario_id={alternative['id']}"
    ).json()
    assert {item["id"] for item in baseline_events} == {
        shared_event.json()["id"],
        baseline_event.json()["id"],
    }
    assert {item["id"] for item in alternative_events} == {
        shared_event.json()["id"],
        alternative_event.json()["id"],
    }

    delete_response = client.delete(f"/projection-scenarios/{alternative['id']}")
    assert delete_response.status_code == 204
    alternative_id = UUID(alternative["id"])
    for model in (SpendingItem, AccountEvent, ProjectionScenarioAccountAssumption):
        count = db_session.scalar(
            select(func.count(model.id)).where(model.scenario_id == alternative_id)
        )
        assert count == 0


def test_projection_uses_selected_scenario_assumptions(
    client: TestClient,
    monkeypatch: MonkeyPatch,
):
    monkeypatch.setattr("app.analytics.projections._current_date", lambda: date(2025, 12, 31))
    household, account = _create_household_and_account(client)
    household_id = household["id"]
    baseline = client.get(f"/households/{household_id}/projection-scenarios").json()[0]
    alternative = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "Higher return"},
    ).json()

    update_assumption = client.put(
        f"/projection-scenarios/{alternative['id']}/account-assumptions/{account['id']}",
        json={"expected_annual_yield": "0.100000"},
    )
    assert update_assumption.status_code == 200
    assert update_assumption.json()["expected_annual_yield"] == "0.100000"

    baseline_projection = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026"
    )
    alternative_projection = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026"
        f"&scenario_id={alternative['id']}"
    )
    assert baseline_projection.status_code == alternative_projection.status_code == 200
    assert baseline_projection.json()["scenario_id"] == baseline["id"]
    assert baseline_projection.json()["scenario_name"] == "Baseline"
    assert alternative_projection.json()["scenario_id"] == alternative["id"]
    assert alternative_projection.json()["scenario_name"] == "Higher return"
    assert baseline_projection.json()["points"][-1]["net_worth"] == "100.00"
    assert alternative_projection.json()["points"][-1]["net_worth"] == "110.00"


def test_property_assumptions_and_sales_are_scenario_specific(client: TestClient):
    household = client.post("/households", json={"name": "Property Scenarios"}).json()
    household_id = household["id"]
    cash = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.050000",
            "currency": "USD",
        },
    ).json()
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
    property_response = client.post(
        "/real-estate/properties",
        json={
            "account_id": home["id"],
            "property_type": "residence",
            "expected_appreciation_rate": "0.030000",
        },
    )
    assert property_response.status_code == 201
    alternative = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "Sell sooner"},
    ).json()

    property_assumption = client.put(
        f"/projection-scenarios/{alternative['id']}/property-assumptions/{home['id']}",
        json={"expected_appreciation_rate": "0.010000"},
    )
    assert property_assumption.status_code == 200
    assert property_assumption.json()["expected_appreciation_rate"] == "0.010000"

    sale_payload = {
        "property_account_id": home["id"],
        "sale_date": "2030-03-01",
        "gross_sale_price": "500000.00",
        "proceeds_account_id": cash["id"],
    }
    baseline_sale = client.post("/real-estate/sales", json=sale_payload)
    alternative_sale = client.post(
        f"/real-estate/sales?scenario_id={alternative['id']}", json=sale_payload
    )
    assert baseline_sale.status_code == alternative_sale.status_code == 201
    assert baseline_sale.json()["scenario_id"] != alternative_sale.json()["scenario_id"]

    baseline_sales = client.get(f"/real-estate/sales?household_id={household_id}").json()
    alternative_sales = client.get(
        f"/real-estate/sales?household_id={household_id}&scenario_id={alternative['id']}"
    ).json()
    assert [sale["id"] for sale in baseline_sales] == [baseline_sale.json()["id"]]
    assert [sale["id"] for sale in alternative_sales] == [alternative_sale.json()["id"]]

    strategy_payload = {
        "enabled": True,
        "optimization_mode": "liquidity_shortfall",
        "priority": 10,
        "proceeds_account_id": cash["id"],
    }
    baseline_strategy = client.put(
        f"/real-estate/liquidation-strategies/{home['id']}", json=strategy_payload
    )
    alternative_strategy = client.put(
        f"/real-estate/liquidation-strategies/{home['id']}?scenario_id={alternative['id']}",
        json=strategy_payload,
    )
    assert baseline_strategy.status_code == alternative_strategy.status_code == 200
    assert baseline_strategy.json()["scenario_id"] != alternative_strategy.json()["scenario_id"]


def test_scenario_settings_income_and_transfers_are_isolated(client: TestClient):
    household, source_account = _create_household_and_account(client)
    household_id = household["id"]
    destination = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Destination",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.050000",
            "currency": "USD",
        },
    ).json()
    alternative = client.post(
        f"/households/{household_id}/projection-scenarios",
        json={"name": "Different cash flow"},
    ).json()

    baseline_settings = client.put(
        f"/projection-settings/{household_id}",
        json={"annual_spending": "1000.00", "spending_mode": "manual"},
    )
    alternative_settings = client.put(
        f"/projection-settings/{household_id}?scenario_id={alternative['id']}",
        json={"annual_spending": "2000.00", "spending_mode": "manual"},
    )
    assert baseline_settings.status_code == alternative_settings.status_code == 200
    assert baseline_settings.json()["scenario_id"] != alternative_settings.json()["scenario_id"]
    assert client.get(f"/projection-settings/{household_id}").json()["annual_spending"] == "1000.00"
    assert (
        client.get(
            f"/projection-settings/{household_id}?scenario_id={alternative['id']}"
        ).json()["annual_spending"]
        == "2000.00"
    )

    income_payload = {
        "household_id": household_id,
        "name": "Salary",
        "amount": "1000.00",
        "frequency": "monthly",
        "start_date": "2026-01-01",
    }
    baseline_income = client.post("/income-sources", json=income_payload)
    alternative_income = client.post(
        f"/income-sources?scenario_id={alternative['id']}", json=income_payload
    )
    assert baseline_income.status_code == alternative_income.status_code == 201
    assert baseline_income.json()["scenario_id"] != alternative_income.json()["scenario_id"]

    transfer_payload = {
        "household_id": household_id,
        "name": "Annual contribution",
        "from_account_id": source_account["id"],
        "to_account_id": destination["id"],
        "annual_amount": "100.00",
        "start_date": "2026-01-01",
    }
    baseline_transfer = client.post("/projection-transfers", json=transfer_payload)
    alternative_transfer = client.post(
        f"/projection-transfers?scenario_id={alternative['id']}", json=transfer_payload
    )
    assert baseline_transfer.status_code == alternative_transfer.status_code == 201
    assert baseline_transfer.json()["scenario_id"] != alternative_transfer.json()["scenario_id"]


def test_cross_household_scenario_cannot_select_projection_inputs(client: TestClient):
    first, _ = _create_household_and_account(client)
    second = client.post("/households", json={"name": "Other Household"}).json()
    other_scenario = client.get(
        f"/households/{second['id']}/projection-scenarios"
    ).json()[0]

    response = client.get(
        f"/dashboard/{first['id']}/projection?start_year=2026&end_year=2026"
        f"&scenario_id={other_scenario['id']}"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Projection scenario not found"
