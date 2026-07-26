from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.projection_withdrawals import LIQUIDITY_CLASSES
from app.analytics.projections import calculate_net_worth_projection


def _liquid_assets_total(point: dict) -> Decimal:
    return sum(
        (
            account["projected_balance"]
            for account in point["accounts"]
            if account["account_kind"] == "asset"
            and account["liquidity_class"] in LIQUIDITY_CLASSES
        ),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))


def _with_summary(projection: dict) -> dict:
    points = projection["points"]
    liquid_totals = [_liquid_assets_total(point) for point in points]
    return {
        **projection,
        "ending_net_worth": points[-1]["net_worth"],
        "lowest_net_worth": min(point["net_worth"] for point in points),
        "lowest_liquid_assets_total": min(liquid_totals),
        "cumulative_projected_income": sum(
            (point["projected_income"] for point in points),
            Decimal("0.00"),
        ),
        "cumulative_projected_taxes": sum(
            (point["projected_taxes"] for point in points),
            Decimal("0.00"),
        ),
        "cumulative_projected_spending": sum(
            (point["projected_spending"] for point in points),
            Decimal("0.00"),
        ),
    }


def compare_projection_scenarios(
    db: Session,
    household_id: UUID,
    *,
    scenario_ids: list[UUID],
    start_year: int,
    end_year: int,
    interval: str,
) -> dict:
    """Run deterministic projections for an ordered set of scenarios and summarize them."""
    scenarios = [
        _with_summary(
            calculate_net_worth_projection(
                db,
                household_id,
                scenario_id=scenario_id,
                start_year=start_year,
                end_year=end_year,
                interval=interval,
            )
        )
        for scenario_id in scenario_ids
    ]
    return {
        "household_id": household_id,
        "start_year": start_year,
        "end_year": end_year,
        "interval": interval,
        "scenarios": scenarios,
    }
