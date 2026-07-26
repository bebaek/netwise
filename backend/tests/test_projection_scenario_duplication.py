from datetime import date
from decimal import Decimal

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountEvent,
    HouseholdPerson,
    IncomeSource,
    ProjectionBehavior,
    ProjectionScenario,
    ProjectionScenarioAccountAssumption,
    ProjectionScenarioPropertyAssumption,
    ProjectionSettings,
    ProjectionTransfer,
    RealEstateLiquidationStrategy,
    RealEstateSale,
    SocialSecurityEstimate,
    SpendingItem,
)
from app.services import projection_scenarios


def _create_account(client: TestClient, household_id: str, name: str, category: str) -> dict:
    return client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": name,
            "account_kind": "asset",
            "category": category,
            "liquidity_class": "illiquid" if category == "real_estate" else "liquid",
            "expected_annual_yield": None if category == "real_estate" else "0.050000",
            "currency": "USD",
        },
    ).json()


def _seed_complete_scenario(client: TestClient, db: Session) -> tuple[dict, ProjectionScenario]:
    household = client.post("/households", json={"name": "Clone Household"}).json()
    household_id = household["id"]
    checking = _create_account(client, household_id, "Checking", "cash")
    brokerage = _create_account(client, household_id, "Brokerage", "taxable_investment")
    home = _create_account(client, household_id, "Home", "real_estate")
    assert (
        client.post(
            "/real-estate/properties",
            json={
                "account_id": home["id"],
                "property_type": "residence",
                "expected_appreciation_rate": "0.030000",
            },
        ).status_code
        == 201
    )
    household_id = UUID(household_id)
    checking["id"] = UUID(checking["id"])
    brokerage["id"] = UUID(brokerage["id"])
    home["id"] = UUID(home["id"])
    baseline = db.scalar(
        select(ProjectionScenario).where(
            ProjectionScenario.household_id == household_id,
            ProjectionScenario.is_baseline.is_(True),
        )
    )
    assert baseline is not None
    person = HouseholdPerson(
        household_id=baseline.household_id,
        name="Alex",
        date_of_birth=date(1970, 1, 1),
    )
    db.add(person)
    db.flush()
    salary = IncomeSource(
        household_id=baseline.household_id,
        scenario_id=baseline.id,
        name="Salary",
        income_type="employment",
        amount=Decimal("120000.00"),
        currency="USD",
        frequency="annual",
        start_date=date(2026, 1, 1),
        deposit_account_id=checking["id"],
    )
    social_income = IncomeSource(
        household_id=baseline.household_id,
        scenario_id=baseline.id,
        name="Alex Social Security",
        income_type="social_security",
        amount=Decimal("24000.00"),
        currency="USD",
        frequency="annual",
        start_date=date(2035, 1, 1),
        deposit_account_id=checking["id"],
    )
    db.add_all([salary, social_income])
    db.flush()
    db.add_all(
        [
            ProjectionSettings(
                household_id=baseline.household_id,
                scenario_id=baseline.id,
                annual_spending=Decimal("60000.00"),
                spending_mode="manual",
                spending_account_id=checking["id"],
            ),
            SpendingItem(
                household_id=baseline.household_id,
                scenario_id=baseline.id,
                name="Housing",
                category="housing",
                annual_amount=Decimal("24000.00"),
            ),
            ProjectionTransfer(
                household_id=baseline.household_id,
                scenario_id=baseline.id,
                name="Invest surplus",
                from_account_id=checking["id"],
                to_account_id=brokerage["id"],
                annual_amount=Decimal("10000.00"),
                start_date=date(2026, 1, 1),
            ),
            RealEstateSale(
                household_id=baseline.household_id,
                scenario_id=baseline.id,
                property_account_id=home["id"],
                sale_date=date(2040, 1, 1),
                gross_sale_price=Decimal("750000.00"),
                proceeds_account_id=brokerage["id"],
            ),
            RealEstateLiquidationStrategy(
                household_id=baseline.household_id,
                scenario_id=baseline.id,
                property_account_id=home["id"],
                enabled=True,
                optimization_mode="liquidity_shortfall",
                priority=10,
                proceeds_account_id=brokerage["id"],
            ),
            AccountEvent(
                household_id=baseline.household_id,
                scenario_id=baseline.id,
                account_id=brokerage["id"],
                event_date=date(2030, 1, 1),
                amount=Decimal("5000.00"),
                currency="USD",
                event_type="contribution",
                projection_behavior=ProjectionBehavior.projection_only,
            ),
            SocialSecurityEstimate(
                household_id=baseline.household_id,
                scenario_id=baseline.id,
                person_id=person.id,
                income_source_id=social_income.id,
                calculation_mode="manual",
                claiming_date=date(2035, 1, 1),
                manual_monthly_benefit=Decimal("2000.00"),
                cola_rate=Decimal("0.020000"),
                estimated_monthly_benefit=Decimal("2000.00"),
                lower_monthly_benefit=Decimal("1800.00"),
                upper_monthly_benefit=Decimal("2200.00"),
                full_retirement_age_months=804,
                benefit_at_full_retirement_age=Decimal("2000.00"),
                calculation_version="manual-v1",
                law_assumption_year=2026,
            ),
        ]
    )
    account_assumption = db.scalar(
        select(ProjectionScenarioAccountAssumption).where(
            ProjectionScenarioAccountAssumption.scenario_id == baseline.id,
            ProjectionScenarioAccountAssumption.account_id == brokerage["id"],
        )
    )
    property_assumption = db.scalar(
        select(ProjectionScenarioPropertyAssumption).where(
            ProjectionScenarioPropertyAssumption.scenario_id == baseline.id
        )
    )
    assert account_assumption is not None
    assert property_assumption is not None
    account_assumption.expected_annual_yield = Decimal("0.071000")
    property_assumption.expected_appreciation_rate = Decimal("0.041000")
    db.commit()
    return household, baseline


def test_duplicate_deep_copies_complete_scenario_and_remaps_income(
    client: TestClient, db_session: Session
) -> None:
    household, baseline = _seed_complete_scenario(client, db_session)

    response = client.post(
        f"/projection-scenarios/{baseline.id}/duplicate",
        json={"name": "Cloned plan", "description": "Independent copy"},
    )
    assert response.status_code == 201
    clone_id = UUID(response.json()["id"])
    assert response.json()["created_from_scenario_id"] == str(baseline.id)

    models = (
        ProjectionSettings,
        SpendingItem,
        IncomeSource,
        SocialSecurityEstimate,
        ProjectionTransfer,
        RealEstateSale,
        RealEstateLiquidationStrategy,
        AccountEvent,
        ProjectionScenarioAccountAssumption,
        ProjectionScenarioPropertyAssumption,
    )
    for model in models:
        source_ids = set(
            db_session.scalars(select(model.id).where(model.scenario_id == baseline.id)).all()
        )
        clone_ids = set(
            db_session.scalars(select(model.id).where(model.scenario_id == clone_id)).all()
        )
        assert len(clone_ids) == len(source_ids)
        assert source_ids.isdisjoint(clone_ids)

    source_social = db_session.scalar(
        select(SocialSecurityEstimate).where(SocialSecurityEstimate.scenario_id == baseline.id)
    )
    cloned_social = db_session.scalar(
        select(SocialSecurityEstimate).where(SocialSecurityEstimate.scenario_id == clone_id)
    )
    assert source_social is not None and cloned_social is not None
    assert cloned_social.income_source_id != source_social.income_source_id
    cloned_income = db_session.get(IncomeSource, cloned_social.income_source_id)
    assert cloned_income is not None
    assert cloned_income.scenario_id == clone_id
    assert cloned_income.name == "Alex Social Security"

    cloned_spending = db_session.scalar(
        select(SpendingItem).where(SpendingItem.scenario_id == clone_id)
    )
    source_spending = db_session.scalar(
        select(SpendingItem).where(SpendingItem.scenario_id == baseline.id)
    )
    assert cloned_spending is not None and source_spending is not None
    cloned_spending.annual_amount = Decimal("30000.00")
    cloned_assumption = db_session.scalar(
        select(ProjectionScenarioAccountAssumption).where(
            ProjectionScenarioAccountAssumption.scenario_id == clone_id,
            ProjectionScenarioAccountAssumption.expected_annual_yield == Decimal("0.071000"),
        )
    )
    assert cloned_assumption is not None
    cloned_assumption.expected_annual_yield = Decimal("0.020000")
    db_session.commit()
    db_session.refresh(source_spending)
    assert source_spending.annual_amount == Decimal("24000.00")
    assert (
        db_session.scalar(
            select(ProjectionScenarioAccountAssumption.expected_annual_yield).where(
                ProjectionScenarioAccountAssumption.scenario_id == baseline.id,
                ProjectionScenarioAccountAssumption.account_id == cloned_assumption.account_id,
            )
        )
        == Decimal("0.071000")
    )

    delegated = client.post(
        f"/households/{household['id']}/projection-scenarios",
        json={"name": "Second clone", "source_scenario_id": str(clone_id)},
    )
    assert delegated.status_code == 201
    assert delegated.json()["created_from_scenario_id"] == str(clone_id)
    assert client.delete(f"/projection-scenarios/{clone_id}").status_code == 204
    surviving_clone = client.get(
        f"/projection-scenarios/{delegated.json()['id']}"
    )
    assert surviving_clone.status_code == 200
    assert surviving_clone.json()["created_from_scenario_id"] is None


def test_duplicate_rolls_back_all_rows_when_copy_fails(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    household = client.post("/households", json={"name": "Rollback"}).json()
    source = db_session.scalar(
        select(ProjectionScenario).where(
            ProjectionScenario.household_id == UUID(household["id"]),
            ProjectionScenario.is_baseline.is_(True),
        )
    )
    assert source is not None

    def fail_after_insert(db: Session, source_record, target) -> None:
        db.add(
            SpendingItem(
                household_id=source_record.household_id,
                scenario_id=target.id,
                name="Partial row",
                category="other",
                annual_amount=Decimal("1.00"),
            )
        )
        db.flush()
        raise RuntimeError("copy failed")

    monkeypatch.setattr(projection_scenarios, "_clone_scenario_records", fail_after_insert)
    with pytest.raises(RuntimeError, match="copy failed"):
        projection_scenarios.duplicate_scenario(
            db_session, source, name="Must roll back"
        )

    assert (
        db_session.scalar(
            select(func.count(ProjectionScenario.id)).where(
                ProjectionScenario.household_id == source.household_id,
                ProjectionScenario.name == "Must roll back",
            )
        )
        == 0
    )
    assert (
        db_session.scalar(
            select(func.count(SpendingItem.id)).where(SpendingItem.name == "Partial row")
        )
        == 0
    )


def test_duplicate_rejects_cross_household_source(client: TestClient) -> None:
    first = client.post("/households", json={"name": "First"}).json()
    second = client.post("/households", json={"name": "Second"}).json()
    second_baseline = client.get(
        f"/households/{second['id']}/projection-scenarios"
    ).json()[0]

    response = client.post(
        f"/households/{first['id']}/projection-scenarios",
        json={"name": "Invalid copy", "source_scenario_id": second_baseline["id"]},
    )
    assert response.status_code == 404
