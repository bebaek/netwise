from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.core.security import AgentPrincipal
from app.db.models import Household
from app.services.agent_tools import summarize_projection_comparison


def test_projection_summary_uses_principal_household_and_omits_yearly_details(
    db_session, monkeypatch
):
    household = Household(name="Projection household")
    db_session.add(household)
    db_session.commit()
    principal = AgentPrincipal(
        api_token_id=uuid4(),
        user_id=uuid4(),
        household_id=household.id,
        scopes=frozenset({"finance:read", "projections:run"}),
        token_name="Projection agent",
        token_prefix="nwt_example",
    )
    scenario_ids = [uuid4(), uuid4()]
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

    monkeypatch.setattr("app.services.agent_tools.compare_projection_scenarios", fake_compare)

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
