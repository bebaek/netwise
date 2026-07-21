from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.analytics.social_security import (
    calculate_ballpark_benefit,
    claiming_adjustment,
    full_retirement_age_months,
)


def test_ballpark_calculator_applies_progressive_formula_and_claiming_adjustment() -> None:
    assert full_retirement_age_months(1960) == 804
    assert claiming_adjustment(62 * 12, 67 * 12) == Decimal("0.7000000000000000000000000000")

    early = calculate_ballpark_benefit(
        date_of_birth=date(1960, 1, 1),
        claiming_date=date(2027, 1, 1),
        current_covered_earnings=Decimal("100000"),
        completed_work_years=35,
        expected_work_end_date=date(2025, 12, 31),
        earnings_pattern="steady",
        cola_rate=Decimal("0.025"),
    )
    at_fra = calculate_ballpark_benefit(
        date_of_birth=date(1960, 1, 1),
        claiming_date=date(2027, 1, 1),
        current_covered_earnings=Decimal("100000"),
        completed_work_years=35,
        expected_work_end_date=date(2025, 12, 31),
        earnings_pattern="steady",
        cola_rate=Decimal("0"),
    )

    assert early.monthly_benefit > Decimal("0")
    assert early.lower_monthly_benefit < early.monthly_benefit < early.upper_monthly_benefit
    assert early.calculation_version == "ssa-ballpark-2025.1"
    assert early.monthly_benefit > at_fra.monthly_benefit


def test_social_security_estimate_creates_projection_income(client: TestClient) -> None:
    household_id = client.post("/households", json={"name": "Retirement"}).json()["id"]
    person_response = client.post(
        "/household-people",
        json={
            "household_id": household_id,
            "name": "Alex",
            "date_of_birth": "1965-06-15",
        },
    )
    assert person_response.status_code == 201
    person_id = person_response.json()["id"]

    estimate_response = client.post(
        "/social-security-estimates",
        json={
            "household_id": household_id,
            "person_id": person_id,
            "calculation_mode": "ballpark",
            "claiming_date": "2032-06-15",
            "current_covered_earnings": "90000.00",
            "completed_work_years": 32,
            "earnings_pattern": "rising",
            "cola_rate": "0.025000",
        },
    )
    assert estimate_response.status_code == 201, estimate_response.text
    estimate = estimate_response.json()
    assert estimate["lower_monthly_benefit"] < estimate["estimated_monthly_benefit"]
    assert estimate["estimated_monthly_benefit"] < estimate["upper_monthly_benefit"]
    assert estimate["full_retirement_age_months"] == 804

    incomes = client.get(f"/income-sources?household_id={household_id}").json()
    assert len(incomes) == 1
    assert incomes[0]["income_type"] == "social_security"
    assert incomes[0]["frequency"] == "monthly"
    assert incomes[0]["start_date"] == "2032-06-15"
    assert incomes[0]["amount"] == estimate["estimated_monthly_benefit"]

    projection_response = client.get(
        f"/dashboard/{household_id}/projection?start_year=2032&end_year=2032"
    )
    assert projection_response.status_code == 200, projection_response.text
    projected_income = Decimal(projection_response.json()["points"][0]["projected_income"])
    assert projected_income == Decimal(estimate["estimated_monthly_benefit"]) * 7

    duplicate_response = client.post(
        "/social-security-estimates",
        json={
            "household_id": household_id,
            "person_id": person_id,
            "calculation_mode": "manual",
            "claiming_date": "2032-06-15",
            "manual_monthly_benefit": "2000.00",
        },
    )
    assert duplicate_response.status_code == 409

    delete_response = client.delete(f"/social-security-estimates/{estimate['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/income-sources?household_id={household_id}").json() == []

    manual_response = client.post(
        "/social-security-estimates",
        json={
            "household_id": household_id,
            "person_id": person_id,
            "calculation_mode": "manual",
            "claiming_date": "2032-06-15",
            "manual_monthly_benefit": "2000.00",
            "cola_rate": "0.020000",
        },
    )
    assert manual_response.status_code == 201, manual_response.text
    manual = manual_response.json()
    assert manual["estimated_monthly_benefit"] == "2000.00"
    assert manual["lower_monthly_benefit"] == "2000.00"
    assert manual["calculation_version"] == "manual-entry-1"

    update_response = client.put(
        f"/social-security-estimates/{manual['id']}",
        json={
            "household_id": household_id,
            "person_id": person_id,
            "calculation_mode": "manual",
            "claiming_date": "2033-01-01",
            "manual_monthly_benefit": "2200.00",
            "cola_rate": "0.030000",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["estimated_monthly_benefit"] == "2200.00"
    incomes = client.get(f"/income-sources?household_id={household_id}").json()
    assert incomes[0]["amount"] == "2200.00"
    assert incomes[0]["start_date"] == "2033-01-01"
    assert incomes[0]["growth_rate"] == "0.030000"


def test_social_security_estimate_rejects_incomplete_ballpark_input(client: TestClient) -> None:
    household_id = client.post("/households", json={"name": "Retirement"}).json()["id"]
    person_id = client.post(
        "/household-people",
        json={
            "household_id": household_id,
            "name": "Sam",
            "date_of_birth": "1970-01-01",
        },
    ).json()["id"]
    response = client.post(
        "/social-security-estimates",
        json={
            "household_id": household_id,
            "person_id": person_id,
            "calculation_mode": "ballpark",
            "claiming_date": "2037-01-01",
        },
    )
    assert response.status_code == 400
    assert "Covered earnings" in response.json()["detail"]
