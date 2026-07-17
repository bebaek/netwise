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


class ProjectionPointRead(BaseModel):
    year: int
    as_of_date: date
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    projected_income: Decimal
    projected_taxes: Decimal
    projected_spending: Decimal
    projected_liquidation_expenses: Decimal
    net_cash_flow: Decimal
    cash_flows: list[ProjectionCashFlowRead]
    accounts: list[ProjectionAccountRead]


class NetWorthProjectionRead(BaseModel):
    household_id: UUID
    start_year: int
    end_year: int
    interval: str
    points: list[ProjectionPointRead]
