import logging

from app.core.logging import HealthcheckAccessLogFilter
from fastapi.testclient import TestClient


def test_healthcheck_access_logs_are_suppressed():
    access_filter = HealthcheckAccessLogFilter()

    assert not access_filter.filter(
        logging.makeLogRecord({"args": ("127.0.0.1", "GET", "/health/live", "1.1", 200)})
    )
    assert not access_filter.filter(
        logging.makeLogRecord({"args": ("127.0.0.1", "GET", "/health/ready?verbose=1", "1.1", 503)})
    )
    assert access_filter.filter(
        logging.makeLogRecord({"args": ("127.0.0.1", "POST", "/accounts", "1.1", 201)})
    )


def test_health(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_update_account(client: TestClient):
    household = client.post("/households", json={"name": "Account Editing"}).json()
    account = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Fidelity",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.050000",
            "currency": "USD",
        },
    ).json()

    response = client.patch(
        f"/accounts/{account['id']}",
        json={
            "category": "retirement",
            "liquidity_class": "retirement_liquid",
            "retirement_tax_treatment": "roth",
            "liquidation_expense_rate": "0.100000",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Fidelity"
    assert updated["category"] == "retirement"
    assert updated["liquidity_class"] == "retirement_liquid"
    assert updated["retirement_tax_treatment"] == "roth"
    assert updated["liquidation_expense_rate"] == "0.100000"


def test_real_estate_account_does_not_store_duplicate_yield(client: TestClient):
    household = client.post("/households", json={"name": "Property Yield"}).json()
    account = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Home",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "illiquid",
            "expected_annual_yield": "0.250000",
        },
    ).json()

    assert account["expected_annual_yield"] is None
    updated = client.patch(
        f"/accounts/{account['id']}", json={"expected_annual_yield": "0.500000"}
    ).json()
    assert updated["expected_annual_yield"] is None


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

    assert (
        client.post(
            f"/accounts/{home['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": "700000.00"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/accounts/{mortgage['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": "450000.00"},
        ).status_code
        == 201
    )

    response = client.get(f"/dashboard/{household_id}/net-worth")

    assert response.status_code == 200
    payload = response.json()
    assert payload["assets_total"] == "700000.00"
    assert payload["liabilities_total"] == "450000.00"
    assert payload["net_worth"] == "250000.00"
    assert len(payload["accounts"]) == 2

    assert (
        client.post(
            f"/accounts/{home['id']}/snapshots",
            json={"as_of_date": "2026-02-01", "balance": "710000.00"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/accounts/{mortgage['id']}/snapshots",
            json={"as_of_date": "2026-02-01", "balance": "448000.00"},
        ).status_code
        == 201
    )

    history_response = client.get(f"/dashboard/{household_id}/net-worth/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["household_id"] == household_id
    assert history["points"] == [
        {
            "as_of_date": "2026-01-01",
            "assets_total": "700000.00",
            "liabilities_total": "450000.00",
            "net_worth": "250000.00",
        },
        {
            "as_of_date": "2026-02-01",
            "assets_total": "710000.00",
            "liabilities_total": "448000.00",
            "net_worth": "262000.00",
        },
    ]

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
    assert property_payload["adjusted_tax_basis"] is None

    property_update_response = client.patch(
        f"/real-estate/properties/{property_payload['id']}",
        json={
            "purchase_date": "2020-02-01",
            "purchase_price": "610000.00",
            "adjusted_tax_basis": "625000.00",
            "down_payment": "125000.00",
            "expected_appreciation_rate": "0.020000",
        },
    )
    assert property_update_response.status_code == 200
    updated_property = property_update_response.json()
    assert updated_property["purchase_date"] == "2020-02-01"
    assert updated_property["purchase_price"] == "610000.00"
    assert updated_property["adjusted_tax_basis"] == "625000.00"
    assert updated_property["down_payment"] == "125000.00"
    assert updated_property["expected_appreciation_rate"] == "0.020000"

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

    income_response = client.post(
        "/income-sources",
        json={
            "household_id": household_id,
            "name": "Salary",
            "income_type": "salary",
            "amount": "120000.00",
            "currency": "USD",
            "frequency": "annually",
            "start_date": "2026-01-01",
            "growth_rate": "0.030000",
        },
    )
    assert income_response.status_code == 201
    income_payload = income_response.json()
    assert income_payload["household_id"] == household_id
    assert income_payload["amount"] == "120000.00"

    incomes_response = client.get(f"/income-sources?household_id={household_id}")
    assert incomes_response.status_code == 200
    assert len(incomes_response.json()) == 1

    tax_response = client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2026,
            "gross_income": "120000.00",
            "total_taxes_paid": "30000.00",
            "refund_or_amount_due": "1000.00",
            "notes": "Initial estimate",
        },
    )
    assert tax_response.status_code == 201
    tax_payload = tax_response.json()
    assert tax_payload["household_id"] == household_id
    assert tax_payload["total_taxes_paid"] == "30000.00"
    assert tax_payload["effective_tax_rate"] == "0.25"

    taxes_response = client.get(f"/annual-tax-records?household_id={household_id}")
    assert taxes_response.status_code == 200
    assert len(taxes_response.json()) == 1


def test_net_worth_history_uses_mortgage_profile_when_no_liability_snapshot(client: TestClient):
    household = client.post("/households", json={"name": "Home"}).json()
    household_id = household["id"]

    home = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "House",
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
            "name": "Mortgage",
            "account_kind": "liability",
            "category": "mortgage",
            "liquidity_class": "liability",
            "currency": "USD",
        },
    ).json()

    assert (
        client.post(
            f"/accounts/{home['id']}/snapshots",
            json={"as_of_date": "2019-12-01", "balance": "390000.00"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/accounts/{home['id']}/snapshots",
            json={"as_of_date": "2020-02-01", "balance": "400000.00"},
        ).status_code
        == 201
    )

    assert (
        client.post(
            "/mortgages",
            json={
                "liability_account_id": mortgage["id"],
                "property_account_id": home["id"],
                "original_principal": "300000.00",
                "interest_rate": "0.000000",
                "term_months": 300,
                "start_date": "2020-01-01",
                "rate_type": "fixed",
            },
        ).status_code
        == 201
    )

    response = client.get(f"/dashboard/{household_id}/net-worth/history")

    assert response.status_code == 200
    assert response.json()["points"] == [
        {
            "as_of_date": "2019-12-01",
            "assets_total": "390000.00",
            "liabilities_total": "0.00",
            "net_worth": "390000.00",
        },
        {
            "as_of_date": "2020-02-01",
            "assets_total": "400000.00",
            "liabilities_total": "299000.00",
            "net_worth": "101000.00",
        },
    ]
