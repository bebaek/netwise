from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.projection_input import load_projection_input
from app.analytics.projections import calculate_net_worth_projection


def test_projection_input_loader_preserves_deterministic_result(
    client: TestClient,
    db_session: Session,
):
    household = client.post("/households", json={"name": "Input Boundary"}).json()
    household_id = UUID(household["id"])
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
    account_id = UUID(account["id"])
    client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2025-12-31", "balance": "1000.00"},
    )
    client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-06-30", "balance": "2000.00"},
    )
    client.post(
        f"/accounts/{account['id']}/events",
        json={
            "event_date": "2026-07-01",
            "amount": "100.00",
            "event_type": "contribution",
            "projection_behavior": "projection_only",
        },
    )
    client.post(
        f"/accounts/{account['id']}/events",
        json={
            "event_date": "2027-01-01",
            "amount": "500.00",
            "event_type": "contribution",
            "projection_behavior": "projection_only",
        },
    )

    projection_input = load_projection_input(
        db_session,
        household_id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )

    assert [item.id for item in projection_input.accounts] == [account_id]
    assert projection_input.initial_balances == {account_id: 1000}
    assert [event.event_date for event in projection_input.projection_events] == [date(2026, 7, 1)]

    loaded_result = calculate_net_worth_projection(
        db_session,
        household_id,
        start_year=2026,
        end_year=2026,
        _projection_data=projection_input,
    )
    direct_result = calculate_net_worth_projection(
        db_session,
        household_id,
        start_year=2026,
        end_year=2026,
    )

    assert loaded_result == direct_result
