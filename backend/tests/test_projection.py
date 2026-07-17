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

def test_projection_models_estimated_spending_income_and_taxes(client: TestClient):
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

    response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2026&end_year=2026"
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["projected_income"] == "100000.00"
    assert point["projected_taxes"] == "20000.00"
    assert point["projected_spending"] == "72100.00"
    assert point["net_cash_flow"] == "7900.00"
    assert point["assets_total"] == "117900.00"
    assert point["net_worth"] == "117900.00"


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
    balances = {account["name"]: account["projected_balance"] for account in point["accounts"]}
    assert balances == {"Brokerage": "43000.00", "Checking": "9000.00"}
    assert point["cash_flows"] == [
        {
            "account_id": checking["id"],
            "account_name": "Checking",
            "cash_flow_type": "income",
            "amount": "10000.00",
        },
        {
            "account_id": checking["id"],
            "account_name": "Checking",
            "cash_flow_type": "tax_payment",
            "amount": "-2000.00",
        },
        {
            "account_id": brokerage["id"],
            "account_name": "Brokerage",
            "cash_flow_type": "spending",
            "amount": "-7000.00",
        },
    ]


def test_projection_rejects_invalid_year_range(client: TestClient):
    household = client.post("/households", json={"name": "Invalid Projection"}).json()

    response = client.get(
        f"/dashboard/{household['id']}/projection?start_year=2030&end_year=2026"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "end_year must be greater than or equal to start_year"
