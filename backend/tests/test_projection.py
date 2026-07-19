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


def test_monthly_projection_returns_month_end_points_and_dates_events(client: TestClient):
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
    assert len(projection["points"]) == 12
    assert projection["points"][0]["as_of_date"] == "2026-01-31"
    assert projection["points"][-1]["as_of_date"] == "2026-12-31"
    assert projection["points"][4]["net_worth"] == "100.00"
    assert projection["points"][5]["net_worth"] == "150.00"


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

    response = client.get(f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026")

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["assets_total"] == "520000.00"
    assert point["liabilities_total"] == "290833.33"
    assert point["net_worth"] == "229166.67"


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
    assert point["projected_taxes"] == "3772.15"
    assert point["projected_spending"] == "7000.00"
    assert point["projected_liquidation_expenses"] == "88.61"
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "41139.24", "Checking": "9000.00"}
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
            "cash_flow_type": "tax_payment",
            "amount": "-1772.15",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "liquidation_expense",
            "amount": "-88.61",
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
    assert point["projected_taxes"] == "2666.67"
    assert point["projected_liquidation_expenses"] == "666.67"
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "36666.66", "Checking": "5000.00"}
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
            "amount": "-2666.67",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "liquidation_expense",
            "amount": "-666.67",
        },
    ]


def test_projection_rejects_invalid_year_range(client: TestClient):
    household = client.post("/households", json={"name": "Invalid Projection"}).json()

    response = client.get(f"/dashboard/{household['id']}/projection?start_year=2030&end_year=2026")

    assert response.status_code == 400
    assert response.json()["detail"] == "end_year must be greater than or equal to start_year"


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
    for account, balance in ((home, "500000.00"), (mortgage, "300000.00")):
        client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": balance},
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
        assert balances["Brokerage"] == "84166.67"
    assert points[0]["projected_taxes"] == "75000.00"
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
            "amount": "-75000.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "property_sale_proceeds",
            "amount": "84166.67",
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
