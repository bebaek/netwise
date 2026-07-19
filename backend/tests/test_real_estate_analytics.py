from fastapi.testclient import TestClient


def test_real_estate_analytics_reports_appreciation_equity_and_estimated_rental_returns(
    client: TestClient,
):
    household = client.post("/households", json={"name": "Property Analytics"}).json()
    household_id = household["id"]
    property_account = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Rental Duplex",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "illiquid",
            "currency": "USD",
        },
    ).json()
    mortgage_account = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Duplex Mortgage",
            "account_kind": "liability",
            "category": "mortgage",
            "liquidity_class": "debt",
            "currency": "USD",
        },
    ).json()
    property_record = client.post(
        "/real-estate/properties",
        json={
            "account_id": property_account["id"],
            "property_type": "rental",
            "purchase_date": "2020-01-01",
            "purchase_price": "400000.00",
            "expected_appreciation_rate": "0.030000",
            "down_payment": "100000.00",
            "is_rental": True,
            "monthly_market_rent": "3000.00",
            "vacancy_rate": "0.050000",
            "management_fee_rate": "0.080000",
            "tax_and_insurance_annual": "6000.00",
            "maintenance_rate": "0.010000",
            "hoa_monthly": "100.00",
            "utilities_annual": "1000.00",
            "other_operating_expense_annual": "500.00",
            "capital_reserve_rate": "0.010000",
        },
    ).json()
    client.post(
        "/mortgages",
        json={
            "liability_account_id": mortgage_account["id"],
            "property_account_id": property_account["id"],
            "original_principal": "300000.00",
            "interest_rate": "0.040000",
            "term_months": 360,
            "start_date": "2020-01-01",
            "monthly_payment": "1500.00",
            "rate_type": "fixed",
        },
    )
    for account_id, balance in (
        (property_account["id"], "450000.00"),
        (mortgage_account["id"], "260000.00"),
    ):
        client.post(
            f"/accounts/{account_id}/snapshots",
            json={"as_of_date": "2023-01-01", "balance": balance},
        )
    for account_id, balance in (
        (property_account["id"], "500000.00"),
        (mortgage_account["id"], "240000.00"),
    ):
        client.post(
            f"/accounts/{account_id}/snapshots",
            json={"as_of_date": "2025-01-01", "balance": balance},
        )

    response = client.get(f"/real-estate/analytics?household_id={household_id}")

    assert response.status_code == 200
    analytics = response.json()
    assert len(analytics) == 1
    result = analytics[0]
    assert result["property_id"] == property_record["id"]
    assert result["property_name"] == "Rental Duplex"
    assert result["valuation_date"] == "2025-01-01"
    assert result["current_value"] == "500000.00"
    assert result["purchase_date"] == "2020-01-01"
    assert result["expected_appreciation_rate"] == "0.030000"
    assert result["appreciation_amount"] == "100000.00"
    assert result["appreciation_rate"] == "0.250000"
    assert result["annualized_appreciation_rate"] == "0.045619"
    assert result["mortgage_balance"] == "240000.00"
    assert result["mortgage_balance_estimated"] is False
    assert result["equity"] == "260000.00"
    assert result["estimated_annual_rental_income"] == "36000.00"
    assert result["estimated_noi"] == "12764.00"
    assert result["estimated_annual_cash_flow"] == "-5236.00"
    assert result["gross_rental_yield"] == "0.072000"
    assert result["cap_rate"] == "0.025528"
    assert result["cash_on_cash_return"] == "-0.052360"
    assert result["valuation_history"] == [
        {"as_of_date": "2023-01-01", "value": "450000.00"},
        {"as_of_date": "2025-01-01", "value": "500000.00"},
    ]
    assert result["limitations"] == [
        "Rental returns use current planning assumptions, not recorded historical income and expenses."
    ]


def test_real_estate_analytics_explains_missing_inputs(client: TestClient):
    household = client.post("/households", json={"name": "Incomplete Property"}).json()
    account = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Land",
            "account_kind": "asset",
            "category": "real_estate",
            "liquidity_class": "illiquid",
            "currency": "USD",
        },
    ).json()
    client.post(
        "/real-estate/properties",
        json={"account_id": account["id"], "property_type": "land"},
    )

    response = client.get(f"/real-estate/analytics?household_id={household['id']}")

    assert response.status_code == 200
    result = response.json()[0]
    assert result["current_value"] is None
    assert result["appreciation_rate"] is None
    assert result["valuation_history"] == []
    assert result["limitations"] == [
        "Add a property valuation snapshot to calculate performance.",
        "Add the purchase price to calculate appreciation.",
        "Add the purchase date to calculate annualized appreciation.",
    ]
