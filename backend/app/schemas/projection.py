from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProjectionAccountRead(BaseModel):
    account_id: UUID
    name: str
    account_kind: str
    category: str
    liquidity_class: str
    projected_balance: Decimal


class ProjectionCashFlowRead(BaseModel):
    account_id: UUID
    account_name: str
    cash_flow_type: str
    amount: Decimal


class ProjectionSpendingItemRead(BaseModel):
    name: str
    category: str
    amount: Decimal


class ProjectionPointRead(BaseModel):
    year: int
    as_of_date: date
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    projected_income: Decimal
    projected_rental_income: Decimal
    projected_rental_expenses: Decimal
    projected_taxes: Decimal
    projected_spending: Decimal
    projected_owner_property_spending: Decimal
    projected_mortgage_spending: Decimal
    projected_spending_breakdown: list[ProjectionSpendingItemRead]
    projected_liquidation_expenses: Decimal
    projected_unfunded_cash_flow: Decimal
    net_cash_flow: Decimal
    retirement_phase: bool
    cash_flows: list[ProjectionCashFlowRead]
    accounts: list[ProjectionAccountRead]


class PropertySaleOptimizationSelectionRead(BaseModel):
    property_account_id: UUID
    property_name: str
    sale_date: date | None


class PropertySaleOptimizationRead(BaseModel):
    mode: str
    candidate_month: int
    candidate_day: int
    schedules_evaluated: int
    first_retirement_withdrawal_date: date | None
    selected_sales: list[PropertySaleOptimizationSelectionRead]


class NetWorthProjectionRead(BaseModel):
    household_id: UUID
    scenario_id: UUID
    scenario_name: str
    start_year: int
    end_year: int
    interval: str
    spending_mode: str
    retirement_date: date | None
    first_retirement_withdrawal_date: date | None
    first_unfunded_date: date | None
    warnings: list[str]
    points: list[ProjectionPointRead]
    property_sale_optimization: PropertySaleOptimizationRead | None = None


class ProjectionComparisonRequest(BaseModel):
    scenario_ids: list[UUID] = Field(min_length=2, max_length=4)
    start_year: int
    end_year: int
    interval: Literal["annual"] = "annual"

    @field_validator("scenario_ids")
    @classmethod
    def scenario_ids_are_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("scenario_ids must be unique")
        return value


class ProjectionComparisonScenarioRead(NetWorthProjectionRead):
    ending_net_worth: Decimal
    lowest_net_worth: Decimal
    lowest_liquid_assets_total: Decimal
    cumulative_projected_income: Decimal
    cumulative_projected_taxes: Decimal
    cumulative_projected_spending: Decimal


class ProjectionComparisonRead(BaseModel):
    household_id: UUID
    start_year: int
    end_year: int
    interval: Literal["annual"]
    scenarios: list[ProjectionComparisonScenarioRead]
