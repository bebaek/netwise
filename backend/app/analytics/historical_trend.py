from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.net_worth import calculate_net_worth_history

MONEY_QUANT = Decimal("0.01")


def calculate_historical_trend(
    db: Session,
    household_id: UUID,
    *,
    interpolate: bool = False,
    interval: str = "month",
) -> dict:
    """Return observed household net worth snapshots plus optional estimates.

    Observed points come from actual balance snapshot dates. Interpolated points are
    derived only for visualization and are clearly marked as estimates.
    """

    if interval != "month":
        raise ValueError("Only monthly interpolation is currently supported")

    history = calculate_net_worth_history(db, household_id)
    observed_points = [
        {
            "as_of_date": point["as_of_date"],
            "net_worth": point["net_worth"],
            "assets_total": point["assets_total"],
            "liabilities_total": point["liabilities_total"],
            "estimated": False,
            "method": None,
        }
        for point in history["points"]
    ]

    if not interpolate or len(observed_points) < 2:
        return {"household_id": household_id, "points": observed_points}

    points = list(observed_points)
    for start, end in zip(observed_points, observed_points[1:], strict=False):
        points.extend(_interpolate_monthly_points(start, end))

    points.sort(key=lambda point: (point["as_of_date"], point["estimated"]))
    return {"household_id": household_id, "points": points}


def _interpolate_monthly_points(start: dict, end: dict) -> list[dict]:
    start_date = start["as_of_date"]
    end_date = end["as_of_date"]
    if start_date >= end_date:
        return []

    total_days = Decimal((end_date - start_date).days)
    current = _next_month_start(start_date)
    estimates = []
    while current < end_date:
        if current != start_date:
            elapsed_days = Decimal((current - start_date).days)
            ratio = elapsed_days / total_days
            estimates.append(
                {
                    "as_of_date": current,
                    "net_worth": _linear_decimal(start["net_worth"], end["net_worth"], ratio),
                    "assets_total": _linear_decimal(start["assets_total"], end["assets_total"], ratio),
                    "liabilities_total": _linear_decimal(
                        start["liabilities_total"], end["liabilities_total"], ratio
                    ),
                    "estimated": True,
                    "method": "linear_interpolation",
                }
            )
        current = _next_month_start(current)
    return estimates


def _next_month_start(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _linear_decimal(start: Decimal, end: Decimal, ratio: Decimal) -> Decimal:
    return (start + ((end - start) * ratio)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
