from fastapi.testclient import TestClient


def test_net_worth_breakdown_history_groups_balances_by_category(client: TestClient):
    household = client.post("/households", json={"name": "Breakdown Home"}).json()
    household_id = household["id"]

    checking = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Checking",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "currency": "USD",
        },
    ).json()
    brokerage = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable",
            "liquidity_class": "liquid",
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

    for account, first_balance, second_balance in [
        (checking, "10000.00", "12000.00"),
        (brokerage, "50000.00", "55000.00"),
        (mortgage, "300000.00", "295000.00"),
    ]:
        assert client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-01-01", "balance": first_balance},
        ).status_code == 201
        assert client.post(
            f"/accounts/{account['id']}/snapshots",
            json={"as_of_date": "2026-02-01", "balance": second_balance},
        ).status_code == 201

    response = client.get(f"/dashboard/{household_id}/breakdown-history")

    assert response.status_code == 200
    assert response.json() == {
        "household_id": household_id,
        "points": [
            {
                "as_of_date": "2026-01-01",
                "assets_total": "60000.00",
                "liabilities_total": "300000.00",
                "net_worth": "-240000.00",
                "asset_categories": [
                    {"category": "cash", "balance": "10000.00"},
                    {"category": "taxable", "balance": "50000.00"},
                ],
                "liability_categories": [{"category": "mortgage", "balance": "300000.00"}],
            },
            {
                "as_of_date": "2026-02-01",
                "assets_total": "67000.00",
                "liabilities_total": "295000.00",
                "net_worth": "-228000.00",
                "asset_categories": [
                    {"category": "cash", "balance": "12000.00"},
                    {"category": "taxable", "balance": "55000.00"},
                ],
                "liability_categories": [{"category": "mortgage", "balance": "295000.00"}],
            },
        ],
    }
