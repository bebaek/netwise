from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.analytics.projections import _withdrawal_order
from app.db.models import Account


def test_default_projection_funding_order():
    accounts = [
        Account(
            id=uuid4(),
            name=name,
            account_kind="asset",
            category=category,
            liquidity_class=liquidity_class,
            retirement_tax_treatment="roth" if name == "Vanguard Roth" else None,
            currency="USD",
        )
        for name, category, liquidity_class in [
            ("Ally", "cash", "marketable"),
            ("401k", "retirement", "retirement_liquid"),
            ("Fidelity", "retirement", "retirement_liquid"),
            ("Vanguard Roth", "retirement", "retirement_liquid"),
            ("Brokerage", "taxable_investment", "marketable"),
            ("Vanguard Stock", "taxable_investment", "marketable"),
            ("Checking", "cash", "liquid"),
        ]
    ]

    assert [account.name for account in _withdrawal_order(accounts, {}, None)] == [
        "Checking",
        "Ally",
        "Brokerage",
        "Vanguard Stock",
        "Vanguard Roth",
        "401k",
        "Fidelity",
    ]

    accounts_by_id = {account.id: account for account in accounts}
    brokerage = next(account for account in accounts if account.name == "Brokerage")
    assert [
        account.name for account in _withdrawal_order(accounts, accounts_by_id, brokerage.id)
    ] == [
        "Brokerage",
        "Vanguard Stock",
        "Vanguard Roth",
        "401k",
        "Fidelity",
    ]


def test_monthly_projection_returns_only_future_month_ends_and_applies_past_events(
    client: TestClient, monkeypatch: MonkeyPatch
):
    monkeypatch.setattr("app.analytics.projections._current_date", lambda: date(2026, 6, 30))
    household = client.post("/households", json={"name": "Monthly Projection"}).json()
    account = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "cash",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "100.00"},
    )
    client.post(
        f"/accounts/{account['id']}/events",
        json={
            "event_date": "2026-06-15",
            "amount": "50.00",
            "event_type": "contribution",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(
        f"/dashboard/{household['id']}/projection?start_year=2026&end_year=2026&interval=monthly"
    )

    assert response.status_code == 200
    projection = response.json()
    assert projection["interval"] == "monthly"
    assert len(projection["points"]) == 6
    assert projection["points"][0]["as_of_date"] == "2026-07-31"
    assert projection["points"][-1]["as_of_date"] == "2026-12-31"
    assert projection["points"][0]["net_worth"] == "150.00"


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

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2027")

    assert response.status_code == 200
    projection = response.json()
    assert projection["start_year"] == 2026
    assert projection["end_year"] == 2027
    assert projection["points"][0]["net_worth"] == "115000.00"
    assert projection["points"][1]["net_worth"] == "126500.00"


def test_projection_event_outflows_use_funding_order_without_negative_balances(client: TestClient):
    household = client.post("/households", json={"name": "Projection Event Spending"}).json()
    household_id = household["id"]

    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "cash",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    savings = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Savings",
            "account_kind": "asset",
            "category": "savings",
            "liquidity_class": "cash",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{checking['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "1000.00"},
    )
    client.post(
        f"/accounts/{savings['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "4000.00"},
    )
    client.post(
        f"/accounts/{checking['id']}/events",
        json={
            "event_date": "2026-06-01",
            "amount": "2500.00",
            "event_type": "large_purchase",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances["Checking"] == "0.00"
    assert balances["Savings"] == "2500.00"
    assert point["net_worth"] == "2500.00"
    assert point["cash_flows"] == [
        {
            "account_id": checking["id"],
            "account_name": "Checking",
            "cash_flow_type": "large_purchase",
            "amount": "-1000.00",
        },
        {
            "account_id": savings["id"],
            "account_name": "Savings",
            "cash_flow_type": "large_purchase",
            "amount": "-1500.00",
        },
    ]


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
            "expected_annual_yield": "0.500000",
            "currency": "USD",
        },
    ).json()
    assert home["expected_annual_yield"] is None
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

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["assets_total"] == "520000.00"
    assert point["liabilities_total"] == "290833.33"
    assert point["net_worth"] == "229166.67"
    assert point["projected_mortgage_spending"] == "9166.63"
    assert point["projected_spending"] == "9166.63"


def test_projection_stops_owner_mortgage_spending_after_final_payment(client: TestClient):
    household = client.post("/households", json={"name": "Mortgage Spending"}).json()
    household_id = household["id"]
    cash = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Cash",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
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
            "expected_annual_yield": "0.000000",
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
    for account, balance in ((cash, "100000.00"), (home, "200000.00"), (mortgage, "12000.00")):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )
    client.post(
        "/real-estate/properties",
        json={
            "account_id": home["id"],
            "property_type": "residence",
            "expected_appreciation_rate": "0.000000",
        },
    )
    client.post(
        "/mortgages",
        json={
            "liability_account_id": mortgage["id"],
            "property_account_id": home["id"],
            "original_principal": "12000.00",
            "interest_rate": "0.000000",
            "term_months": 12,
            "start_date": "2025-12-01",
            "monthly_payment": "1000.00",
            "rate_type": "fixed",
        },
    )

    response = client.get(
        f"/dashboard/{household_id}/projection"
        "?start_year=2026&end_year=2027&annual_spending=12000.00&spending_inflation_rate=0.100000"
    )

    assert response.status_code == 200
    points = response.json()["points"]
    assert points[0]["projected_mortgage_spending"] == "12000.00"
    assert points[0]["projected_spending"] == "24000.00"
    assert points[1]["projected_mortgage_spending"] == "0.00"
    assert points[1]["projected_spending"] == "13200.00"
    cash_balances = [
        next(account["projected_balance"] for account in point["accounts"] if account["name"] == "Cash")
        for point in points
    ]
    assert cash_balances == ["76000.00", "62800.00"]


def test_projection_does_not_infer_spending_from_historical_snapshots(client: TestClient):
    household = client.post("/households", json={"name": "Spending Projection"}).json()
    household_id = household["id"]

    cash = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Cash",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{cash['id']}/snapshots",
        json={"as_of_date": "2025-01-01", "balance": "100000.00"},
    )
    client.post(
        f"/accounts/{cash['id']}/snapshots",
        json={"as_of_date": "2025-12-31", "balance": "110000.00"},
    )
    client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2025,
            "gross_income": "100000.00",
            "total_taxes_paid": "20000.00",
        },
    )
    client.post(
        "/income-sources",
        json={
            "household_id": household_id,
            "name": "Salary",
            "amount": "100000.00",
            "frequency": "annually",
            "start_date": "2026-01-01",
            "growth_rate": "0.000000",
        },
    )

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_income"] == "100000.00"
    assert point["projected_taxes"] == "20000.00"
    assert point["projected_spending"] == "0.00"
    assert point["net_cash_flow"] == "80000.00"
    assert point["assets_total"] == "190000.00"
    assert point["net_worth"] == "190000.00"


def test_projection_uses_itemized_spending_and_retirement_amounts(client: TestClient):
    household = client.post("/households", json={"name": "Itemized Spending"}).json()
    household_id = household["id"]
    cash = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Cash",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{cash['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "100000.00"},
    )
    settings_response = client.put(
        f"/projection-settings/{household_id}",
        json={
            "annual_spending": "50000.00",
            "spending_inflation_rate": "0.100000",
            "retirement_date": "2027-01-01",
            "retirement_annual_spending": "22000.00",
        },
    )
    assert settings_response.status_code == 200
    for payload in (
        {
            "household_id": household_id,
            "name": "Food",
            "category": "food",
            "annual_amount": "12000.00",
            "retirement_annual_amount": "10000.00",
        },
        {
            "household_id": household_id,
            "name": "Travel",
            "category": "travel",
            "annual_amount": "6000.00",
            "retirement_annual_amount": "12000.00",
            "growth_rate": "0.000000",
        },
    ):
        assert client.post("/spending-items", json=payload).status_code == 201

    manual_response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026"
    )
    assert manual_response.status_code == 200
    manual_point = manual_response.json()["points"][0]
    assert manual_response.json()["spending_mode"] == "manual"
    assert manual_point["projected_spending"] == "50000.00"
    assert manual_point["projected_spending_breakdown"] == [
        {
            "name": "Unitemized non-mortgage spending",
            "category": "other",
            "amount": "50000.00",
        }
    ]

    itemized_settings_response = client.put(
        f"/projection-settings/{household_id}",
        json={
            "annual_spending": "50000.00",
            "spending_mode": "itemized",
            "spending_inflation_rate": "0.100000",
            "retirement_date": "2027-01-01",
            "retirement_annual_spending": "22000.00",
        },
    )
    assert itemized_settings_response.status_code == 200

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2027"
    )

    assert response.status_code == 200
    points = response.json()["points"]
    assert response.json()["spending_mode"] == "itemized"
    assert points[0]["projected_spending"] == "18000.00"
    assert points[0]["projected_spending_breakdown"] == [
        {"name": "Food", "category": "food", "amount": "12000.00"},
        {"name": "Travel", "category": "travel", "amount": "6000.00"},
    ]
    assert points[1]["projected_spending"] == "23000.00"
    assert points[1]["projected_spending_breakdown"] == [
        {"name": "Food", "category": "food", "amount": "11000.00"},
        {"name": "Travel", "category": "travel", "amount": "12000.00"},
    ]

    override_response = client.get(
        f"/dashboard/{household_id}/projection"
        "?start_year=2026&end_year=2026&annual_spending=24000.00"
    )
    assert override_response.status_code == 200
    override_point = override_response.json()["points"][0]
    assert override_response.json()["spending_mode"] == "manual"
    assert override_point["projected_spending"] == "24000.00"
    assert override_point["projected_spending_breakdown"] == [
        {
            "name": "Unitemized non-mortgage spending",
            "category": "other",
            "amount": "24000.00",
        }
    ]


def test_spending_item_crud(client: TestClient):
    household = client.post("/households", json={"name": "Spending CRUD"}).json()
    create_response = client.post(
        "/spending-items",
        json={
            "household_id": household["id"],
            "name": "  Groceries  ",
            "category": "Food",
            "annual_amount": "9000.00",
        },
    )
    assert create_response.status_code == 201
    spending_item = create_response.json()
    assert spending_item["name"] == "Groceries"
    assert spending_item["category"] == "food"

    list_response = client.get(f"/spending-items?household_id={household['id']}")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [spending_item["id"]]

    update_response = client.patch(
        f"/spending-items/{spending_item['id']}",
        json={"annual_amount": "9600.00", "retirement_annual_amount": "8400.00"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["annual_amount"] == "9600.00"
    assert update_response.json()["retirement_annual_amount"] == "8400.00"

    projection_response = client.get(
        f"/dashboard/{household['id']}/projection?start_year=2026&end_year=2026"
    )
    assert projection_response.status_code == 200
    assert projection_response.json()["spending_mode"] == "itemized"
    assert projection_response.json()["points"][0]["projected_spending"] == "9600.00"

    delete_response = client.delete(f"/spending-items/{spending_item['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/spending-items?household_id={household['id']}").json() == []


def test_projection_accepts_explicit_spending_assumption(client: TestClient):
    household = client.post("/households", json={"name": "Spending Assumption"}).json()
    household_id = household["id"]

    cash = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Cash",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{cash['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "100000.00"},
    )

    response = client.get(
        f"/dashboard/{household_id}/projection"
        "?start_year=2026&end_year=2027&annual_spending=12000.00&spending_inflation_rate=0.100000"
    )

    assert response.status_code == 200
    points = response.json()["points"]
    assert points[0]["projected_spending"] == "12000.00"
    assert points[0]["net_worth"] == "88000.00"
    assert points[1]["projected_spending"] == "13200.00"
    assert points[1]["net_worth"] == "74800.00"


def test_projection_applies_income_taxes_and_spending_to_selected_accounts(client: TestClient):
    household = client.post("/households", json={"name": "Account Cash Flow"}).json()
    household_id = household["id"]

    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "brokerage",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{checking['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "1000.00"},
    )
    client.post(
        f"/accounts/{brokerage['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "50000.00"},
    )
    client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2025,
            "gross_income": "100000.00",
            "total_taxes_paid": "20000.00",
        },
    )
    income = client.post(
        "/income-sources",
        json={
            "household_id": household_id,
            "name": "Salary",
            "amount": "10000.00",
            "frequency": "annually",
            "start_date": "2026-01-01",
            "growth_rate": "0.000000",
            "deposit_account_id": checking["id"],
        },
    )
    assert income.status_code == 201

    response = client.get(
        f"/dashboard/{household_id}/projection"
        "?start_year=2026&end_year=2026&annual_spending=7000.00"
        f"&tax_account_id={checking['id']}&spending_account_id={brokerage['id']}"
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_income"] == "10000.00"
    assert point["projected_taxes"] == "2000.00"
    assert point["projected_spending"] == "7000.00"
    assert point["projected_liquidation_expenses"] == "70.71"
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "42929.29", "Checking": "9000.00"}
    assert point["cash_flows"] == [
        {
            "account_id": checking["id"],
            "account_name": "Checking",
            "cash_flow_type": "income",
            "amount": "10000.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "spending",
            "amount": "-7000.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "liquidation_expense",
            "amount": "-70.71",
        },
        {
            "account_id": checking["id"],
            "account_name": "Checking",
            "cash_flow_type": "tax_payment",
            "amount": "-2000.00",
        },
    ]


def test_projection_uses_persisted_cash_flow_settings(client: TestClient):
    household = client.post("/households", json={"name": "Persisted Projection Settings"}).json()
    household_id = household["id"]

    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    savings = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Savings",
            "account_kind": "asset",
            "category": "savings",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{checking['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "10000.00"},
    )
    client.post(
        f"/accounts/{savings['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "20000.00"},
    )
    client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2025,
            "gross_income": "100000.00",
            "total_taxes_paid": "10000.00",
        },
    )
    client.post(
        "/income-sources",
        json={
            "household_id": household_id,
            "name": "Salary",
            "amount": "10000.00",
            "frequency": "annually",
            "start_date": "2026-01-01",
            "growth_rate": "0.000000",
            "deposit_account_id": checking["id"],
        },
    )
    settings = client.put(
        f"/projection-settings/{household_id}",
        json={
            "annual_spending": "6000.00",
            "spending_inflation_rate": "0.100000",
            "spending_account_id": savings["id"],
            "tax_account_id": checking["id"],
        },
    )
    assert settings.status_code == 200
    assert settings.json()["annual_spending"] == "6000.00"

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2027")

    assert response.status_code == 200
    points = response.json()["points"]
    assert points[0]["projected_spending"] == "6000.00"
    assert points[1]["projected_spending"] == "6600.00"
    final_balances = {
        account["name"]: account["projected_balance"] for account in points[1]["accounts"]
    }
    assert final_balances == {"Checking": "28000.00", "Savings": "7400.00"}


def test_projection_switches_spending_at_retirement_and_reports_withdrawal(
    client: TestClient, monkeypatch: MonkeyPatch
):
    monkeypatch.setattr("app.analytics.projections._current_date", lambda: date(2025, 12, 31))
    household_id = client.post("/households", json={"name": "Retirement Phase"}).json()["id"]
    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    retirement = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Traditional IRA",
            "account_kind": "asset",
            "category": "retirement",
            "liquidity_class": "retirement_liquid",
            "retirement_tax_treatment": "traditional",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    for account, balance in ((checking, "600.00"), (retirement, "1000.00")):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )

    settings = client.put(
        f"/projection-settings/{household_id}",
        json={
            "annual_spending": "1200.00",
            "spending_inflation_rate": "0.000000",
            "retirement_date": "2026-07-16",
            "retirement_annual_spending": "600.00",
        },
    )
    assert settings.status_code == 200
    assert settings.json()["retirement_date"] == "2026-07-16"
    assert settings.json()["retirement_annual_spending"] == "600.00"

    response = client.get(
        f"/dashboard/{household_id}/projection"
        "?start_year=2026&end_year=2026&interval=monthly"
    )

    assert response.status_code == 200
    projection = response.json()
    assert projection["retirement_date"] == "2026-07-16"
    assert projection["first_retirement_withdrawal_date"] == "2026-07-31"
    assert projection["first_unfunded_date"] is None
    assert [point["projected_spending"] for point in projection["points"]] == [
        "100.00",
        "100.00",
        "100.00",
        "100.00",
        "100.00",
        "100.00",
        "74.19",
        "50.00",
        "50.00",
        "50.00",
        "50.00",
        "50.00",
    ]
    assert projection["points"][5]["retirement_phase"] is False
    assert projection["points"][6]["retirement_phase"] is True
    assert projection["points"][-1]["projected_liquidation_expenses"] == "0.00"
    balances = {
        account["name"]: account["projected_balance"]
        for account in projection["points"][-1]["accounts"]
    }
    assert balances == {"Checking": "0.00", "Traditional IRA": "675.81"}


def test_recurring_projection_transfer_moves_available_cash_without_changing_net_worth(
    client: TestClient, monkeypatch: MonkeyPatch
):
    monkeypatch.setattr("app.analytics.projections._current_date", lambda: date(2025, 12, 31))
    household_id = client.post("/households", json={"name": "Recurring Contributions"}).json()["id"]
    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    retirement = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "401k",
            "account_kind": "asset",
            "category": "retirement",
            "liquidity_class": "retirement_liquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    for account, balance in ((checking, "150.00"), (retirement, "0.00")):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )

    created = client.post(
        "/projection-transfers",
        json={
            "household_id": household_id,
            "name": "401k contribution",
            "from_account_id": checking["id"],
            "to_account_id": retirement["id"],
            "annual_amount": "1200.00",
            "start_date": "2026-03-15",
            "end_date": "2026-04-01",
            "growth_rate": "0.000000",
        },
    )
    assert created.status_code == 201
    transfer_id = created.json()["id"]
    listed = client.get(f"/projection-transfers?household_id={household_id}")
    assert listed.status_code == 200
    assert [transfer["id"] for transfer in listed.json()] == [transfer_id]

    response = client.get(
        f"/dashboard/{household_id}/projection"
        "?start_year=2026&end_year=2026&interval=monthly"
    )

    assert response.status_code == 200
    points = response.json()["points"]
    assert all(point["net_worth"] == "150.00" for point in points)
    assert points[1]["cash_flows"] == []
    assert [flow["cash_flow_type"] for flow in points[2]["cash_flows"]] == [
        "recurring_transfer_out",
        "recurring_transfer_in",
    ]
    assert [flow["amount"] for flow in points[2]["cash_flows"]] == ["-100.00", "100.00"]
    assert [flow["amount"] for flow in points[3]["cash_flows"]] == ["-50.00", "50.00"]
    final_balances = {
        account["name"]: account["projected_balance"] for account in points[-1]["accounts"]
    }
    assert final_balances == {"401k": "150.00", "Checking": "0.00"}

    deleted = client.delete(f"/projection-transfers/{transfer_id}")
    assert deleted.status_code == 204


def test_projection_taxes_non_cash_projection_event_withdrawals(client: TestClient):
    household = client.post("/households", json={"name": "Taxable Withdrawal"}).json()
    household_id = household["id"]

    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "brokerage",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.050000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{checking['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "5000.00"},
    )
    client.post(
        f"/accounts/{brokerage['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "50000.00"},
    )
    client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2025,
            "gross_income": "100000.00",
            "total_taxes_paid": "20000.00",
        },
    )
    client.post(
        f"/accounts/{brokerage['id']}/events",
        json={
            "event_date": "2026-06-01",
            "amount": "10000.00",
            "event_type": "withdrawal",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026"
        f"&tax_account_id={checking['id']}"
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_taxes"] == "0.00"
    assert point["projected_liquidation_expenses"] == "526.32"
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "39473.68", "Checking": "5000.00"}
    # Zero-gain basis fallback: the full withdrawal is return of capital, so
    # only the liquidation expense applies; no tax_payment cash flow.
    assert point["cash_flows"] == [
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "withdrawal",
            "amount": "-10000.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "liquidation_expense",
            "amount": "-526.32",
        },
    ]


def test_projection_rejects_invalid_year_range(client: TestClient):
    household = client.post("/households", json={"name": "Invalid Projection"}).json()

    response = client.get(f"/dashboard/{household['id']}/projection?start_year=2030&end_year=2026")

    assert response.status_code == 400
    assert response.json()["detail"] == "end_year must be greater than or equal to start_year"


def test_taxable_investment_withdrawals_tax_only_capital_gains(client: TestClient):
    household = client.post("/households", json={"name": "Capital Gains"}).json()
    household_id = household["id"]
    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "brokerage",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{checking['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "0.00"},
    )
    client.post(
        f"/accounts/{brokerage['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "100000.00"},
    )
    client.patch(
        f"/accounts/{brokerage['id']}",
        json={"cost_basis": "80000.00"},
    )
    client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2025,
            "gross_income": "100000.00",
            "total_taxes_paid": "20000.00",
        },
    )
    client.post(
        f"/accounts/{brokerage['id']}/events",
        json={
            "event_date": "2026-06-01",
            "amount": "10000.00",
            "event_type": "withdrawal",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026"
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    # 20% embedded gain taxed at 15% capital gains, not 20% income on the full amount.
    # Rounded-up gross withdrawal (10309.28) keeps net funding at exactly $10,000.
    assert point["projected_taxes"] == "309.28"
    assert point["projected_liquidation_expenses"] == "0.00"
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "89690.72", "Checking": "0.00"}
    assert point["cash_flows"] == [
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "withdrawal",
            "amount": "-10000.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "tax_payment",
            "amount": "-309.28",
        },
    ]


def test_projection_uses_oldest_snapshot_as_cost_basis_estimate(client: TestClient):
    household = client.post("/households", json={"name": "Basis Fallback"}).json()
    household_id = household["id"]
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
            "currency": "USD",
        },
    ).json()
    for as_of_date, balance in (
        ("2024-01-01", "60000.00"),
        ("2025-01-01", "75000.00"),
        ("2026-01-01", "90000.00"),
    ):
        client.post(
            f"/accounts/{brokerage['id']}/snapshots",
            json={"as_of_date": as_of_date, "balance": balance},
        )
    client.post(
        f"/accounts/{brokerage['id']}/events",
        json={
            "event_date": "2026-06-01",
            "amount": "9000.00",
            "event_type": "withdrawal",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    # Oldest snapshot ($60,000) becomes the estimated basis: 1/3 of the $90,000
    # balance is embedded gain, taxed at 15% instead of the income tax rate.
    # Rounded-up gross withdrawal (9473.68) keeps net funding at exactly $9,000.
    assert point["projected_taxes"] == "473.68"
    assert response.json()["warnings"] == [
        "Taxable investment cost basis estimated from oldest balance snapshots for: Brokerage. "
        "Enter an explicit cost basis on each account for more accurate capital gains taxes."
    ]
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "80526.31"}


def test_explicit_cost_basis_overrides_snapshot_estimate(client: TestClient):
    household = client.post("/households", json={"name": "Explicit Basis"}).json()
    household_id = household["id"]
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
            "currency": "USD",
        },
    ).json()
    for as_of_date, balance in (
        ("2024-01-01", "60000.00"),
        ("2026-01-01", "90000.00"),
    ):
        client.post(
            f"/accounts/{brokerage['id']}/snapshots",
            json={"as_of_date": as_of_date, "balance": balance},
        )
    update_response = client.patch(
        f"/accounts/{brokerage['id']}",
        json={"cost_basis": "90000.00"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["cost_basis"] == "90000.00"
    client.post(
        f"/accounts/{brokerage['id']}/events",
        json={
            "event_date": "2026-06-01",
            "amount": "9000.00",
            "event_type": "withdrawal",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_taxes"] == "0.00"
    assert response.json()["warnings"] == []
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "81000.00"}


def test_property_sale_proceeds_become_cost_basis(client: TestClient):
    household_id = client.post("/households", json={"name": "Sale Proceeds Basis"}).json()["id"]
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "brokerage",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
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
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
        },
    ).json()
    for account, balance in ((brokerage, "0.00"), (home, "100000.00")):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )
    client.post(
        "/real-estate/properties",
        json={
            "account_id": home["id"],
            "property_type": "residence",
            "adjusted_tax_basis": "100000.00",
        },
    )
    client.post(
        "/real-estate/sales",
        json={
            "property_account_id": home["id"],
            "sale_date": "2026-06-01",
            "gross_sale_price": "100000.00",
            "selling_expense_rate": "0.000000",
            "estimated_tax_rate": "0.000000",
        },
    )
    client.post(
        f"/accounts/{brokerage['id']}/events",
        json={
            "event_date": "2026-06-02",
            "amount": "50000.00",
            "event_type": "withdrawal",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    # Sale proceeds carry their own basis, so spending them is not taxed again.
    assert point["projected_taxes"] == "0.00"
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "50000.00", "Home": "0.00"}


def test_property_sale_transfers_net_proceeds_and_pays_off_mortgage(client: TestClient):
    household_id = client.post("/households", json={"name": "Property Sale"}).json()["id"]
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "brokerage",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
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
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.100000",
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
            "expected_annual_yield": "0.000000",
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
        f"/accounts/{brokerage['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "0.00"},
    )
    property_response = client.post(
        "/real-estate/properties",
        json={
            "account_id": home["id"],
            "property_type": "residence",
            "purchase_price": "275000.00",
            "adjusted_tax_basis": "300000.00",
        },
    )
    assert property_response.status_code == 201
    client.post(
        "/mortgages",
        json={
            "liability_account_id": mortgage["id"],
            "property_account_id": home["id"],
            "original_principal": "300000.00",
            "interest_rate": "0.000000",
            "term_months": 360,
            "start_date": "2026-01-01",
        },
    )

    sale_response = client.post(
        "/real-estate/sales",
        json={
            "property_account_id": home["id"],
            "sale_date": "2026-06-01",
            "gross_sale_price": "500000.00",
        },
    )
    assert sale_response.status_code == 201
    assert sale_response.json()["proceeds_account_id"] == brokerage["id"]
    assert sale_response.json()["estimated_tax_rate"] == "0.150000"

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2027")
    assert response.status_code == 200
    points = response.json()["points"]
    for point in points:
        balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
        assert balances["Home"] == "0.00"
        assert balances["Mortgage"] == "0.00"
        assert balances["Brokerage"] == "136666.67"
    assert points[0]["projected_taxes"] == "22500.00"
    assert response.json()["warnings"] == [
        "Taxable investment cost basis estimated from oldest balance snapshots for: Brokerage. "
        "Enter an explicit cost basis on each account for more accurate capital gains taxes."
    ]
    assert points[0]["cash_flows"] == [
        {
            "account_id": home["id"],
            "account_name": "Home",
            "cash_flow_type": "property_sale_removal",
            "amount": "-500000.00",
        },
        {
            "account_id": mortgage["id"],
            "account_name": "Mortgage",
            "cash_flow_type": "mortgage_payoff",
            "amount": "-290833.33",
        },
        {
            "account_id": home["id"],
            "account_name": "Home",
            "cash_flow_type": "property_sale_expense",
            "amount": "-50000.00",
        },
        {
            "account_id": home["id"],
            "account_name": "Home",
            "cash_flow_type": "property_sale_tax",
            "amount": "-22500.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "property_sale_proceeds",
            "amount": "136666.67",
        },
    ]


def test_default_withdrawals_do_not_liquidate_real_estate(client: TestClient):
    household_id = client.post("/households", json={"name": "No Implicit Home Sale"}).json()["id"]
    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
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
            "expected_annual_yield": "0.000000",
        },
    ).json()
    retirement = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Retirement",
            "account_kind": "asset",
            "category": "retirement",
            "liquidity_class": "retirement_liquid",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
        },
    ).json()
    for account, balance in ((checking, "1000.00"), (home, "10000.00"), (retirement, "1000.00")):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )
    client.post(
        f"/accounts/{checking['id']}/events",
        json={
            "event_date": "2026-06-01",
            "amount": "1500.00",
            "event_type": "large_purchase",
            "projection_behavior": "projection_only",
        },
    )

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")
    assert response.status_code == 200
    balances = {
        account["name"]: account["projected_balance"]
        for account in response.json()["points"][0]["accounts"]
    }
    assert balances == {"Checking": "0.00", "Home": "10000.00", "Retirement": "500.00"}


def test_automatic_property_sale_funds_shortfall_before_retirement(client: TestClient):
    household_id = client.post("/households", json={"name": "Automatic Property Sale"}).json()["id"]
    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    retirement = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Retirement",
            "account_kind": "asset",
            "category": "retirement",
            "liquidity_class": "retirement_liquid",
            "retirement_tax_treatment": "traditional",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    rental = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Rental",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "illiquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    for account, balance in ((checking, "100.00"), (retirement, "10000.00"), (rental, "1000.00")):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )

    strategy_response = client.put(
        f"/real-estate/liquidation-strategies/{rental['id']}",
        json={
            "priority": 1,
            "earliest_sale_date": "2026-01-01",
            "proceeds_account_id": checking["id"],
        },
    )
    assert strategy_response.status_code == 200
    assert strategy_response.json()["estimated_tax_rate"] == "0.150000"

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026&annual_spending=500.00"
    )

    assert response.status_code == 200
    assert response.json()["warnings"] == [
        "Rental: sale tax uses the gross-price fallback because tax basis is missing."
    ]
    point = response.json()["points"][0]
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Checking": "390.00", "Rental": "0.00", "Retirement": "10000.00"}
    assert point["projected_taxes"] == "150.00"
    assert point["projected_liquidation_expenses"] == "60.00"
    assert point["projected_unfunded_cash_flow"] == "0.00"
    assert [flow["cash_flow_type"] for flow in point["cash_flows"]] == [
        "spending",
        "automatic_property_sale_removal",
        "automatic_property_sale_expense",
        "automatic_property_sale_tax",
        "automatic_property_sale_proceeds",
        "spending",
    ]


def test_property_sale_optimizer_excludes_past_march_dates_and_reports_schedule(
    client: TestClient, monkeypatch: MonkeyPatch
):
    monkeypatch.setattr("app.analytics.projections._current_date", lambda: date(2026, 3, 2))
    household_id = client.post("/households", json={"name": "Runway Optimizer"}).json()["id"]
    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    stock = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Stock",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.100000",
            "liquidation_expense_rate": "0.000000",
        },
    ).json()
    rental = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Rental",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "illiquid",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
        },
    ).json()
    retirement = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Retirement",
            "account_kind": "asset",
            "category": "retirement",
            "liquidity_class": "retirement_liquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    for account, balance in (
        (checking, "100.00"),
        (stock, "0.00"),
        (rental, "1000.00"),
        (retirement, "1000.00"),
    ):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )

    strategy_response = client.put(
        f"/real-estate/liquidation-strategies/{rental['id']}",
        json={
            "optimization_mode": "maximize_liquid_runway",
            "priority": 1,
            "proceeds_account_id": stock["id"],
            "selling_expense_rate": "0.000000",
            "estimated_tax_rate": "0.000000",
        },
    )
    assert strategy_response.status_code == 200
    assert strategy_response.json()["optimization_mode"] == "maximize_liquid_runway"

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2027&annual_spending=100.00"
    )

    assert response.status_code == 200
    optimization = response.json()["property_sale_optimization"]
    assert optimization["schedules_evaluated"] == 2
    assert optimization["selected_sales"] == [
        {
            "property_account_id": rental["id"],
            "property_name": "Rental",
            "sale_date": "2027-03-01",
        }
    ]
    assert optimization["first_retirement_withdrawal_date"] is None
    sale_flows = [
        flow
        for point in response.json()["points"]
        for flow in point["cash_flows"]
        if flow["cash_flow_type"] == "automatic_property_sale_proceeds"
    ]
    assert len(sale_flows) == 1
    assert sale_flows[0]["account_name"] == "Stock"


def test_projection_reports_unfunded_cash_flow(client: TestClient):
    household_id = client.post("/households", json={"name": "Unfunded Projection"}).json()["id"]
    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
        },
    ).json()
    client.post(
        f"/accounts/{checking['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "100.00"},
    )

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026&annual_spending=500.00"
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_unfunded_cash_flow"] == "400.00"
    assert point["cash_flows"][0]["amount"] == "-100.00"


def test_rental_cash_flow_prorates_start_month_and_funds_shortfall_without_negative_accounts(
    client: TestClient,
):
    household = client.post("/households", json={"name": "Rental Funding"}).json()
    household_id = household["id"]

    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "checking",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable_investment",
            "liquidity_class": "marketable",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
            "currency": "USD",
        },
    ).json()
    rental = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Rental",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "illiquid",
            "expected_annual_yield": "0.000000",
            "currency": "USD",
        },
    ).json()
    for account_id, balance in [
        (checking["id"], "100.00"),
        (brokerage["id"], "1000.00"),
        (rental["id"], "100000.00"),
    ]:
        client.post(
            f"/accounts/{account_id}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
        )
    client.post(
        f"/accounts/{rental['id']}/snapshots",
        json={"as_of_date": "2026-07-01", "balance": "100000.00"},
    )
    property_response = client.post(
        "/real-estate/properties",
        json={
            "account_id": rental["id"],
            "property_type": "rental",
            "is_rental": True,
            "rental_start_date": "2026-06-01",
            "monthly_market_rent": "100.00",
            "rent_growth_rate": "0.000000",
            "vacancy_rate": "0.000000",
            "other_operating_expense_annual": "2400.00",
            "rental_deposit_account_id": checking["id"],
        },
    )
    assert property_response.status_code == 201

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_rental_income"] == "700.00"
    assert point["projected_rental_expenses"] == "1400.00"
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "400.00", "Checking": "0.00", "Rental": "100000.00"}
    assert all(float(balance) >= 0 for balance in balances.values())
    assert point["cash_flows"] == [
        {
            "account_id": checking["id"],
            "account_name": "Checking",
            "cash_flow_type": "rental_income",
            "amount": "700.00",
        },
        {
            "account_id": checking["id"],
            "account_name": "Checking",
            "cash_flow_type": "rental_expense",
            "amount": "-800.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "rental_expense",
            "amount": "-600.00",
        },
    ]


def test_roth_withdrawals_are_tax_free(client: TestClient):
    household = client.post("/households", json={"name": "Tax-Free Roth"}).json()
    household_id = household["id"]
    roth = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Vanguard IRA",
            "account_kind": "asset",
            "category": "retirement",
            "liquidity_class": "retirement_liquid",
            "retirement_tax_treatment": "roth",
            "expected_annual_yield": "0.000000",
            "liquidation_expense_rate": "0.000000",
            "currency": "USD",
        },
    ).json()
    client.post(
        f"/accounts/{roth['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "10000.00"},
    )
    client.post(
        "/annual-tax-records",
        json={
            "household_id": household_id,
            "tax_year": 2025,
            "gross_income": "100000.00",
            "total_taxes_paid": "20000.00",
        },
    )

    response = client.get(
        f"/dashboard/{household_id}/projection"
        "?start_year=2026&end_year=2026&annual_spending=1000.00"
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_taxes"] == "0.00"
    assert point["projected_liquidation_expenses"] == "0.00"
    assert point["accounts"][0]["projected_balance"] == "9000.00"
    assert point["cash_flows"] == [
        {
            "account_id": roth["id"],
            "account_name": "Vanguard IRA",
            "cash_flow_type": "spending",
            "amount": "-1000.00",
        }
    ]
