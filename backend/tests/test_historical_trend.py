from fastapi.testclient import TestClient


def test_historical_trend_returns_snapshots_by_default_and_optional_estimates(client: TestClient):
    household = client.post("/households", json={"name": "Trend Home"}).json()
    account = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Brokerage",
            "account_kind": "asset",
            "category": "taxable",
            "liquidity_class": "liquid",
            "currency": "USD",
        },
    ).json()

    assert client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-01-01", "balance": "1000.00"},
    ).status_code == 201
    assert client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-04-01", "balance": "1300.00"},
    ).status_code == 201

    snapshot_response = client.get(f"/dashboard/{household['id']}/historical-trend")
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["points"] == [
        {
            "as_of_date": "2026-01-01",
            "assets_total": "1000.00",
            "liabilities_total": "0.00",
            "net_worth": "1000.00",
            "estimated": False,
            "method": None,
        },
        {
            "as_of_date": "2026-04-01",
            "assets_total": "1300.00",
            "liabilities_total": "0.00",
            "net_worth": "1300.00",
            "estimated": False,
            "method": None,
        },
    ]

    estimate_response = client.get(f"/dashboard/{household['id']}/historical-trend?interpolate=true")
    assert estimate_response.status_code == 200
    assert estimate_response.json()["points"] == [
        {
            "as_of_date": "2026-01-01",
            "assets_total": "1000.00",
            "liabilities_total": "0.00",
            "net_worth": "1000.00",
            "estimated": False,
            "method": None,
        },
        {
            "as_of_date": "2026-02-01",
            "assets_total": "1103.33",
            "liabilities_total": "0.00",
            "net_worth": "1103.33",
            "estimated": True,
            "method": "linear_interpolation",
        },
        {
            "as_of_date": "2026-03-01",
            "assets_total": "1196.67",
            "liabilities_total": "0.00",
            "net_worth": "1196.67",
            "estimated": True,
            "method": "linear_interpolation",
        },
        {
            "as_of_date": "2026-04-01",
            "assets_total": "1300.00",
            "liabilities_total": "0.00",
            "net_worth": "1300.00",
            "estimated": False,
            "method": None,
        },
    ]
