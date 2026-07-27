from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import select

from app.core.security import AgentPrincipal
from app.db.models import (
    Account,
    BalanceSnapshot,
    Household,
    MortgageProfile,
    ProjectionScenario,
    ProjectionScenarioPropertyAssumption,
    ProjectionSettings,
    RealEstateProperty,
)
from app.services.agent_tools import record_account_balance
from app.services.projection_agent_tools import (
    check_projection_readiness,
    get_property_projection_parameters,
    list_projection_scenarios,
    summarize_projection_assumptions,
    summarize_projection_comparison,
)


def _agent_principal(household: Household, *scopes: str) -> AgentPrincipal:
    return AgentPrincipal(
        api_token_id=uuid4(),
        user_id=uuid4(),
        household_id=household.id,
        scopes=frozenset(scopes),
        token_name="Agent tool test",
        token_prefix="nwt_example",
    )


def _account(household: Household, name: str = "Checking") -> Account:
    return Account(
        household=household,
        name=name,
        account_kind="asset",
        category="cash",
        liquidity_class="liquid",
        currency="USD",
        is_active=True,
    )


def test_projection_summary_uses_principal_household_and_omits_yearly_details(
    db_session, monkeypatch
):
    household = Household(name="Projection household")
    baseline = ProjectionScenario(household=household, name="Baseline", is_baseline=True)
    alternative = ProjectionScenario(household=household, name="Retire Early", is_baseline=False)
    db_session.add_all([household, baseline, alternative])
    db_session.commit()
    principal = _agent_principal(household, "finance:read", "projections:run")
    scenario_ids = [baseline.id, alternative.id]
    captured: dict[str, object] = {}

    def fake_compare(
        db,
        household_id,
        *,
        scenario_ids,
        start_year,
        end_year,
        interval,
    ):
        captured.update(
            {
                "db": db,
                "household_id": household_id,
                "scenario_ids": scenario_ids,
                "start_year": start_year,
                "end_year": end_year,
                "interval": interval,
            }
        )
        return {
            "household_id": household_id,
            "start_year": start_year,
            "end_year": end_year,
            "interval": interval,
            "scenarios": [
                {
                    "scenario_id": scenario_ids[0],
                    "scenario_name": "Baseline",
                    "ending_net_worth": Decimal("2000000.00"),
                    "lowest_net_worth": Decimal("750000.00"),
                    "lowest_liquid_assets_total": Decimal("125000.00"),
                    "cumulative_projected_income": Decimal("900000.00"),
                    "cumulative_projected_taxes": Decimal("175000.00"),
                    "cumulative_projected_spending": Decimal("600000.00"),
                    "retirement_date": date(2030, 1, 1),
                    "first_unfunded_date": None,
                    "warnings": ["Example warning"],
                    "points": [{"must_not": "be returned"}],
                    "accounts": [{"must_not": "be returned"}],
                }
            ],
        }

    monkeypatch.setattr(
        "app.services.projection_agent_tools.compare_projection_scenarios", fake_compare
    )

    result = summarize_projection_comparison(
        db_session,
        principal,
        [str(scenario_id) for scenario_id in scenario_ids],
        2026,
        2050,
    )

    assert captured == {
        "db": db_session,
        "household_id": household.id,
        "scenario_ids": scenario_ids,
        "start_year": 2026,
        "end_year": 2050,
        "interval": "annual",
    }
    assert result == {
        "household_id": str(household.id),
        "start_year": 2026,
        "end_year": 2050,
        "scenarios": [
            {
                "scenario_id": str(scenario_ids[0]),
                "scenario_name": "Baseline",
                "ending_net_worth": "2000000.00",
                "lowest_net_worth": "750000.00",
                "lowest_liquid_assets_total": "125000.00",
                "cumulative_projected_income": "900000.00",
                "cumulative_projected_taxes": "175000.00",
                "cumulative_projected_spending": "600000.00",
                "retirement_date": "2030-01-01",
                "first_unfunded_date": None,
                "warnings": ["Example warning"],
            }
        ],
    }


def test_projection_discovery_and_comparison_accept_scenario_names(db_session, monkeypatch):
    household = Household(name="Scenario discovery household")
    baseline = ProjectionScenario(household=household, name="Baseline", is_baseline=True)
    alternative = ProjectionScenario(household=household, name="Retire Early", is_baseline=False)
    db_session.add_all([household, baseline, alternative])
    db_session.commit()
    principal = _agent_principal(household, "finance:read", "projections:run")
    captured: dict[str, object] = {}

    def fake_compare(db, household_id, **kwargs):
        captured.update(kwargs)
        return {
            "household_id": household_id,
            "start_year": kwargs["start_year"],
            "end_year": kwargs["end_year"],
            "scenarios": [],
        }

    monkeypatch.setattr(
        "app.services.projection_agent_tools.compare_projection_scenarios", fake_compare
    )

    discovered = list_projection_scenarios(db_session, principal)
    compared = summarize_projection_comparison(
        db_session,
        principal,
        None,
        2026,
        2030,
        scenarios=["baseline", "Retire Early"],
    )

    assert [item["name"] for item in discovered["scenarios"]] == ["Baseline", "Retire Early"]
    assert captured["scenario_ids"] == [baseline.id, alternative.id]
    assert compared["scenarios"] == []


def test_projection_assumptions_property_parameters_and_readiness(db_session):
    household = Household(name="Property projection household")
    baseline = ProjectionScenario(household=household, name="Baseline", is_baseline=True)
    property_account = Account(
        household=household,
        name="Lake House",
        account_kind="asset",
        category="real_estate",
        liquidity_class="illiquid",
        currency="USD",
        is_active=True,
    )
    mortgage_account = Account(
        household=household,
        name="Lake House Mortgage",
        account_kind="liability",
        category="mortgage",
        liquidity_class="illiquid",
        currency="USD",
        is_active=True,
    )
    db_session.add_all([household, baseline, property_account, mortgage_account])
    db_session.flush()
    property_record = RealEstateProperty(
        household_id=household.id,
        account=property_account,
        property_type="residence",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("400000.00"),
        adjusted_tax_basis=Decimal("410000.00"),
        expected_appreciation_rate=Decimal("0.030000"),
        property_tax_annual=Decimal("8000.00"),
        insurance_annual=Decimal("2400.00"),
        maintenance_rate=Decimal("0.010000"),
        is_rental=False,
    )
    mortgage = MortgageProfile(
        household_id=household.id,
        liability_account_id=mortgage_account.id,
        property_account_id=property_account.id,
        original_principal=Decimal("300000.00"),
        interest_rate=Decimal("0.040000"),
        term_months=360,
        start_date=date(2020, 1, 1),
        monthly_payment=Decimal("1432.25"),
        rate_type="fixed",
    )
    assumption = ProjectionScenarioPropertyAssumption(
        scenario_id=baseline.id,
        household_id=household.id,
        property_account_id=property_account.id,
        expected_appreciation_rate=Decimal("0.025000"),
        rent_growth_rate=None,
        vacancy_rate=None,
    )
    settings = ProjectionSettings(
        household_id=household.id,
        scenario_id=baseline.id,
        annual_spending=Decimal("60000.00"),
        spending_mode="manual",
        spending_inflation_rate=Decimal("0.025000"),
    )
    property_snapshot = BalanceSnapshot(
        household_id=household.id,
        account=property_account,
        as_of_date=date(2026, 1, 1),
        balance=Decimal("500000.00"),
        currency="USD",
        source="manual",
    )
    mortgage_snapshot = BalanceSnapshot(
        household_id=household.id,
        account=mortgage_account,
        as_of_date=date(2026, 1, 1),
        balance=Decimal("250000.00"),
        currency="USD",
        source="manual",
    )
    db_session.add_all(
        [
            property_record,
            mortgage,
            assumption,
            settings,
            property_snapshot,
            mortgage_snapshot,
        ]
    )
    db_session.commit()
    principal = _agent_principal(household, "finance:read", "projections:run")

    assumptions = summarize_projection_assumptions(
        db_session,
        principal,
        "baseline",
        ["settings", "properties"],
    )
    parameters = get_property_projection_parameters(
        db_session,
        principal,
        "lake house",
        "Baseline",
    )
    readiness = check_projection_readiness(db_session, principal, str(baseline.id))

    assert assumptions["settings"]["annual_spending"] == "60000.00"
    assert assumptions["properties"] == [
        {
            "property_name": "Lake House",
            "property_type": "residence",
            "is_rental": False,
            "expected_appreciation_rate": "0.025000",
            "rent_growth_rate": None,
            "vacancy_rate": None,
        }
    ]
    assert parameters["property"]["latest_value"] == "500000.00"
    assert parameters["property"]["expected_appreciation_rate"] == "0.025000"
    assert parameters["mortgage"]["latest_balance"] == "250000.00"
    assert parameters["mortgage"]["interest_rate"] == "0.040000"
    assert readiness["ready"] is True
    assert readiness["issue_counts"] == {"errors": 0, "warnings": 1}
    assert readiness["issues"][0]["code"] == "missing_tax_history"


def test_record_account_balance_previews_then_saves_exact_confirmation(db_session):
    household = Household(name="Balance household")
    account = _account(household)
    db_session.add_all([household, account])
    db_session.commit()
    principal = _agent_principal(household, "finance:read", "finance:write")

    preview = record_account_balance(
        db_session,
        principal,
        " checking ",
        "1234.5",
        "2020-01-15",
    )

    assert preview == {
        "status": "confirmation_required",
        "action": "create",
        "account_name": "Checking",
        "as_of_date": "2020-01-15",
        "balance": "1234.50",
        "currency": "USD",
        "existing_balance": None,
        "required_confirmation": "CONFIRM CREATE Checking 2020-01-15 1234.50 USD",
        "instruction": (
            "Show this preview to the user and ask them to reply with the exact confirmation "
            "text. Do not call this tool again until the user supplies it verbatim in a "
            "subsequent message."
        ),
    }
    assert db_session.scalar(select(BalanceSnapshot)) is None

    wrong_confirmation = record_account_balance(
        db_session,
        principal,
        "Checking",
        "1234.50",
        "2020-01-15",
        "yes",
    )
    assert wrong_confirmation == preview
    assert db_session.scalar(select(BalanceSnapshot)) is None

    saved = record_account_balance(
        db_session,
        principal,
        "Checking",
        "1234.50",
        "2020-01-15",
        preview["required_confirmation"],
    )
    assert saved == {
        "status": "saved",
        "action": "create",
        "account_name": "Checking",
        "as_of_date": "2020-01-15",
        "balance": "1234.50",
        "currency": "USD",
        "created_count": 1,
        "updated_count": 0,
    }
    snapshot = db_session.scalar(select(BalanceSnapshot))
    assert snapshot.household_id == household.id
    assert snapshot.account_id == account.id
    assert snapshot.balance == Decimal("1234.50")
    assert snapshot.source == "manual"
    assert snapshot.confidence_level == "confirmed_by_user"

    update_preview = record_account_balance(
        db_session,
        principal,
        "Checking",
        "1300.00",
        "2020-01-15",
    )
    assert update_preview["required_confirmation"] == (
        "CONFIRM UPDATE Checking 2020-01-15 1300.00 USD REPLACING 1234.50"
    )
    updated = record_account_balance(
        db_session,
        principal,
        "Checking",
        "1300.00",
        "2020-01-15",
        update_preview["required_confirmation"],
    )
    assert updated["status"] == "saved"
    assert updated["action"] == "update"
    assert updated["created_count"] == 0
    assert updated["updated_count"] == 1
    db_session.refresh(snapshot)
    assert snapshot.balance == Decimal("1300.00")


@pytest.mark.parametrize("balance", ["1.001", "NaN", "10000000000000000", "not-money"])
def test_record_account_balance_rejects_invalid_money(db_session, balance):
    household = Household(name="Invalid balance household")
    account = _account(household)
    db_session.add_all([household, account])
    db_session.commit()
    principal = _agent_principal(household, "finance:read", "finance:write")

    with pytest.raises(ValueError):
        record_account_balance(
            db_session,
            principal,
            "Checking",
            balance,
            "2020-01-15",
        )
    assert db_session.scalar(select(BalanceSnapshot)) is None


def test_record_account_balance_rejects_stale_update_confirmation(db_session):
    household = Household(name="Stale confirmation household")
    account = _account(household)
    db_session.add_all([household, account])
    db_session.flush()
    snapshot = BalanceSnapshot(
        household_id=household.id,
        account=account,
        as_of_date=date(2020, 1, 15),
        balance=Decimal("100.00"),
        currency="USD",
        source="manual",
    )
    db_session.add(snapshot)
    db_session.commit()
    principal = _agent_principal(household, "finance:read", "finance:write")

    preview = record_account_balance(
        db_session,
        principal,
        "Checking",
        "150.00",
        "2020-01-15",
    )
    assert preview["required_confirmation"] == (
        "CONFIRM UPDATE Checking 2020-01-15 150.00 USD REPLACING 100.00"
    )

    snapshot.balance = Decimal("125.00")
    db_session.commit()
    stale_attempt = record_account_balance(
        db_session,
        principal,
        "Checking",
        "150.00",
        "2020-01-15",
        preview["required_confirmation"],
    )

    assert stale_attempt["status"] == "confirmation_required"
    assert stale_attempt["existing_balance"] == "125.00"
    assert stale_attempt["required_confirmation"] == (
        "CONFIRM UPDATE Checking 2020-01-15 150.00 USD REPLACING 125.00"
    )
    db_session.refresh(snapshot)
    assert snapshot.balance == Decimal("125.00")


def test_record_account_balance_requires_both_scopes_and_bound_household(db_session):
    household = Household(name="Bound household")
    other = Household(name="Other household")
    other_account = _account(other, "Other checking")
    db_session.add_all([household, other, other_account])
    db_session.commit()

    missing_write = _agent_principal(household, "finance:read")
    with pytest.raises(HTTPException) as exc_info:
        record_account_balance(
            db_session,
            missing_write,
            "Other checking",
            "1.00",
            "2020-01-15",
        )
    assert exc_info.value.status_code == 403

    principal = _agent_principal(household, "finance:read", "finance:write")
    with pytest.raises(ValueError, match="must identify exactly one account"):
        record_account_balance(
            db_session,
            principal,
            "Other checking",
            "1.00",
            "2020-01-15",
        )
    assert db_session.scalar(select(BalanceSnapshot)) is None
