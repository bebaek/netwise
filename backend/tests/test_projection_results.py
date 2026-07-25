from datetime import date
from decimal import Decimal
from uuid import UUID

from app.analytics.projection_results import (
    ProjectionAccountResult,
    ProjectionCashFlowResult,
    ProjectionPointResult,
    ProjectionResult,
    ProjectionSpendingItemResult,
    PropertySaleOptimizationResult,
    PropertySaleOptimizationSelectionResult,
    format_projection_result,
)
from app.db.models import AccountKind
from app.schemas.projection import NetWorthProjectionRead

HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")
ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")
PROPERTY_ID = UUID("00000000-0000-0000-0000-000000000003")


def test_format_projection_result_translates_nested_simulation_records() -> None:
    point = ProjectionPointResult(
        year=2030,
        as_of_date=date(2030, 12, 31),
        net_worth=Decimal("10100.00"),
        assets_total=Decimal("10100.00"),
        liabilities_total=Decimal("0.00"),
        projected_income=Decimal("1000.00"),
        projected_rental_income=Decimal("0.00"),
        projected_rental_expenses=Decimal("0.00"),
        projected_taxes=Decimal("100.00"),
        projected_spending=Decimal("500.00"),
        projected_owner_property_spending=Decimal("0.00"),
        projected_mortgage_spending=Decimal("0.00"),
        projected_spending_breakdown=(
            ProjectionSpendingItemResult(
                name="Living expenses",
                category="other",
                amount=Decimal("500.00"),
            ),
        ),
        projected_liquidation_expenses=Decimal("0.00"),
        projected_unfunded_cash_flow=Decimal("0.00"),
        net_cash_flow=Decimal("400.00"),
        retirement_phase=False,
        cash_flows=(
            ProjectionCashFlowResult(
                account_id=ACCOUNT_ID,
                account_name="Checking",
                cash_flow_type="income",
                amount=Decimal("1000.00"),
            ),
        ),
        accounts=(
            ProjectionAccountResult(
                account_id=ACCOUNT_ID,
                name="Checking",
                account_kind=AccountKind.asset,
                category="cash",
                liquidity_class="cash",
                projected_balance=Decimal("10100.00"),
            ),
        ),
    )
    result = ProjectionResult(
        household_id=HOUSEHOLD_ID,
        start_year=2030,
        end_year=2030,
        interval="annual",
        spending_mode="manual",
        retirement_date=None,
        first_retirement_withdrawal_date=None,
        first_unfunded_date=None,
        warnings=("Example warning",),
        points=(point,),
        property_sale_optimization=PropertySaleOptimizationResult(
            mode="maximize_liquid_runway",
            candidate_month=3,
            candidate_day=1,
            schedules_evaluated=2,
            first_retirement_withdrawal_date=None,
            selected_sales=(
                PropertySaleOptimizationSelectionResult(
                    property_account_id=PROPERTY_ID,
                    property_name="Rental",
                    sale_date=date(2030, 3, 1),
                ),
            ),
        ),
    )

    response = format_projection_result(result)

    assert response["warnings"] == ["Example warning"]
    assert response["points"][0]["cash_flows"] == [
        {
            "account_id": ACCOUNT_ID,
            "account_name": "Checking",
            "cash_flow_type": "income",
            "amount": Decimal("1000.00"),
        }
    ]
    assert response["points"][0]["projected_spending_breakdown"] == [
        {
            "name": "Living expenses",
            "category": "other",
            "amount": Decimal("500.00"),
        }
    ]
    assert response["property_sale_optimization"]["selected_sales"] == [
        {
            "property_account_id": PROPERTY_ID,
            "property_name": "Rental",
            "sale_date": date(2030, 3, 1),
        }
    ]
    assert NetWorthProjectionRead.model_validate(response).household_id == HOUSEHOLD_ID


def test_format_projection_result_omits_absent_optimization() -> None:
    result = ProjectionResult(
        household_id=HOUSEHOLD_ID,
        start_year=2030,
        end_year=2030,
        interval="annual",
        spending_mode="manual",
        retirement_date=None,
        first_retirement_withdrawal_date=None,
        first_unfunded_date=None,
        warnings=(),
        points=(),
    )

    response = format_projection_result(result)

    assert "property_sale_optimization" not in response
    assert response["warnings"] == []
    assert response["points"] == []
