from datetime import date
from decimal import Decimal
from uuid import uuid4


def _create_household(client, name: str) -> dict:
    response = client.post("/households", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _baseline(client, household_id: str) -> dict:
    response = client.get(f"/households/{household_id}/projection-scenarios")
    assert response.status_code == 200
    return next(item for item in response.json() if item["is_baseline"])


def test_projection_comparison_is_deterministic_and_computes_server_summaries(client):
    household = _create_household(client, "Comparison Household")
    household_id = household["id"]
    baseline = _baseline(client, household_id)

    account_response = client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": "Comparison Checking",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "expected_annual_yield": "0.010000",
            "currency": "USD",
        },
    )
    assert account_response.status_code == 201
    account = account_response.json()
    current_year = date.today().year
    snapshot_response = client.post(
        f"/accounts/{account['id']}/snapshots",
        json={
            "as_of_date": date(current_year - 1, 12, 31).isoformat(),
            "balance": "10000.00",
            "currency": "USD",
        },
    )
    assert snapshot_response.status_code == 201

    duplicate_response = client.post(
        f"/projection-scenarios/{baseline['id']}/duplicate",
        json={"name": "Higher return"},
    )
    assert duplicate_response.status_code == 201
    alternative = duplicate_response.json()
    assumption_response = client.put(
        f"/projection-scenarios/{alternative['id']}/account-assumptions/{account['id']}",
        json={"expected_annual_yield": "0.100000", "liquidation_expense_rate": "0.000000"},
    )
    assert assumption_response.status_code == 200

    payload = {
        "scenario_ids": [baseline["id"], alternative["id"]],
        "start_year": current_year,
        "end_year": current_year + 2,
        "interval": "annual",
    }
    first_response = client.post(
        f"/dashboard/{household_id}/projection-comparison",
        json=payload,
    )
    assert first_response.status_code == 200
    first = first_response.json()
    assert [item["scenario_id"] for item in first["scenarios"]] == payload["scenario_ids"]
    assert [item["scenario_name"] for item in first["scenarios"]] == [
        "Baseline",
        "Higher return",
    ]

    for scenario in first["scenarios"]:
        points = scenario["points"]
        assert Decimal(scenario["ending_net_worth"]) == Decimal(points[-1]["net_worth"])
        assert Decimal(scenario["lowest_net_worth"]) == min(
            Decimal(point["net_worth"]) for point in points
        )
        liquid_totals = [
            sum(
                (
                    Decimal(account_point["projected_balance"])
                    for account_point in point["accounts"]
                    if account_point["account_kind"] == "asset"
                    and account_point["liquidity_class"]
                    in {"cash", "liquid", "marketable", "retirement_liquid"}
                ),
                Decimal("0.00"),
            )
            for point in points
        ]
        assert Decimal(scenario["lowest_liquid_assets_total"]) == min(liquid_totals)
        assert Decimal(scenario["cumulative_projected_income"]) == sum(
            (Decimal(point["projected_income"]) for point in points),
            Decimal("0.00"),
        )
        assert Decimal(scenario["cumulative_projected_taxes"]) == sum(
            (Decimal(point["projected_taxes"]) for point in points),
            Decimal("0.00"),
        )
        assert Decimal(scenario["cumulative_projected_spending"]) == sum(
            (Decimal(point["projected_spending"]) for point in points),
            Decimal("0.00"),
        )

    assert Decimal(first["scenarios"][1]["ending_net_worth"]) > Decimal(
        first["scenarios"][0]["ending_net_worth"]
    )
    second_response = client.post(
        f"/dashboard/{household_id}/projection-comparison",
        json=payload,
    )
    assert second_response.status_code == 200
    assert second_response.json() == first


def test_projection_comparison_validates_scenario_set_and_household_ownership(client):
    first_household = _create_household(client, "First Comparison Household")
    second_household = _create_household(client, "Second Comparison Household")
    first_baseline = _baseline(client, first_household["id"])
    second_baseline = _baseline(client, second_household["id"])
    current_year = date.today().year
    endpoint = f"/dashboard/{first_household['id']}/projection-comparison"
    alternatives = []
    for index in range(3):
        response = client.post(
            f"/households/{first_household['id']}/projection-scenarios",
            json={"name": f"Comparison option {index + 1}"},
        )
        assert response.status_code == 201
        alternatives.append(response.json())

    valid_four = client.post(
        endpoint,
        json={
            "scenario_ids": [first_baseline["id"], *(item["id"] for item in alternatives)],
            "start_year": current_year,
            "end_year": current_year + 1,
        },
    )
    assert valid_four.status_code == 200
    assert len(valid_four.json()["scenarios"]) == 4

    too_few = client.post(
        endpoint,
        json={
            "scenario_ids": [first_baseline["id"]],
            "start_year": current_year,
            "end_year": current_year + 1,
        },
    )
    assert too_few.status_code == 422

    too_many = client.post(
        endpoint,
        json={
            "scenario_ids": [first_baseline["id"], *(str(uuid4()) for _ in range(4))],
            "start_year": current_year,
            "end_year": current_year + 1,
        },
    )
    assert too_many.status_code == 422

    duplicate = client.post(
        endpoint,
        json={
            "scenario_ids": [first_baseline["id"], first_baseline["id"]],
            "start_year": current_year,
            "end_year": current_year + 1,
        },
    )
    assert duplicate.status_code == 422
    assert "scenario_ids must be unique" in duplicate.text

    non_annual = client.post(
        endpoint,
        json={
            "scenario_ids": [first_baseline["id"], second_baseline["id"]],
            "start_year": current_year,
            "end_year": current_year + 1,
            "interval": "monthly",
        },
    )
    assert non_annual.status_code == 422

    unauthorized = client.post(
        endpoint,
        json={
            "scenario_ids": [first_baseline["id"], second_baseline["id"]],
            "start_year": current_year,
            "end_year": current_year + 1,
        },
    )
    assert unauthorized.status_code == 400
    assert unauthorized.json()["detail"] == "Projection scenario not found"
    assert second_baseline["name"] not in unauthorized.text

    invalid_years = client.post(
        endpoint,
        json={
            "scenario_ids": [first_baseline["id"], second_baseline["id"]],
            "start_year": current_year + 1,
            "end_year": current_year,
        },
    )
    assert invalid_years.status_code == 400
    assert "end_year" in invalid_years.json()["detail"]
