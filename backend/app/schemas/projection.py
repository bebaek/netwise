from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


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
