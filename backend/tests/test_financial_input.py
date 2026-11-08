from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas.account import BalanceSnapshotCreate, BalanceSnapshotUpdate
from app.schemas.planning import SpendingItemUpdate
from app.schemas.real_estate import RealEstatePropertyUpdate


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12,234.56", "12234.56"),
        (" 1,234,567.89 ", "1234567.89"),
        ("-12,234.56", "-12234.56"),
        ("+1,234", "1234"),
        ("1234.56", "1234.56"),
        ("0", "0"),
        ("999,999,999,999,999.99", "999999999999999.99"),
    ],
)
def test_grouped_balance_preserves_decimal_precision(text, expected):
    snapshot = BalanceSnapshotCreate(as_of_date=date(2026, 11, 8), balance=text)
    assert snapshot.balance == Decimal(expected)
    assert snapshot.model_dump(mode="json")["balance"] == expected


@pytest.mark.parametrize(
    "text",
    [
        "12,23.56",
        "1,,234",
        "1234,567",
        "1.234,56",
        "1,234.",
        "$1,234.56",
        "1,234.567",
        "1,234e3",
        "12,345,678,901,234,567.89",
    ],
)
def test_invalid_grouping_and_existing_precision_limits_are_rejected(text):
    with pytest.raises(ValidationError):
        BalanceSnapshotCreate(as_of_date=date(2026, 11, 8), balance=text)


def test_optional_fields_and_constraints_are_preserved():
    assert BalanceSnapshotUpdate(balance=None).balance is None
    assert BalanceSnapshotUpdate().model_dump(exclude_unset=True) == {}
    assert SpendingItemUpdate(annual_amount="12,234.56").annual_amount == Decimal("12234.56")
    assert RealEstatePropertyUpdate(purchase_price="123,456.78").purchase_price == Decimal(
        "123456.78"
    )
    with pytest.raises(ValidationError):
        RealEstatePropertyUpdate(purchase_price="-1,234.56")


def test_grouped_financial_values_round_trip_through_api(client: TestClient):
    household = client.post("/households", json={"name": "Grouped amounts"}).json()
    account_response = client.post(
        "/accounts",
        json={
            "household_id": household["id"],
            "name": "Investment 12,234.56",
            "account_kind": "asset",
            "category": "education",
            "liquidity_class": "restricted",
            "cost_basis": "10,000.00",
        },
    )
    assert account_response.status_code == 201
    account = account_response.json()
    assert account["name"] == "Investment 12,234.56"
    assert account["cost_basis"] == "10000.00"

    response = client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-11-08", "balance": "12,234.56"},
    )
    assert response.status_code == 201
    snapshot = response.json()
    assert snapshot["balance"] == "12234.56"

    response = client.patch(
        f"/accounts/{account['id']}/snapshots/{snapshot['id']}",
        json={"balance": "13,234.56"},
    )
    assert response.status_code == 200
    assert response.json()["balance"] == "13234.56"

    response = client.post(
        f"/households/{household['id']}/snapshot-batch",
        json={
            "as_of_date": "2026-11-09",
            "snapshots": [
                {"account_id": account["id"], "balance": "14,234.56"},
            ],
        },
    )
    assert response.status_code == 201
    assert response.json()["snapshots"][0]["balance"] == "14234.56"

    response = client.post(
        f"/accounts/{account['id']}/events",
        json={"event_date": "2026-11-09", "amount": "1,234.56", "event_type": "contribution"},
    )
    assert response.status_code == 201
    assert response.json()["amount"] == "1234.56"

    response = client.post(
        f"/accounts/{account['id']}/snapshots",
        json={"as_of_date": "2026-11-10", "balance": "12,23.56"},
    )
    assert response.status_code == 422
