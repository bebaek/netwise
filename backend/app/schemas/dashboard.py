from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class AccountBalanceRead(BaseModel):
    account_id: UUID
    name: str
    account_kind: str
    category: str
    liquidity_class: str
    balance: Decimal | None
    signed_balance: Decimal


class NetWorthRead(BaseModel):
    household_id: UUID
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    accounts: list[AccountBalanceRead]


class NetWorthHistoryPointRead(BaseModel):
    as_of_date: date
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal


class HistoricalTrendPointRead(BaseModel):
    as_of_date: date
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    estimated: bool
    method: str | None = None


class HistoricalTrendRead(BaseModel):
    household_id: UUID
    points: list[HistoricalTrendPointRead]


class NetWorthHistoryRead(BaseModel):
    household_id: UUID
    points: list[NetWorthHistoryPointRead]


class CategoryBalanceRead(BaseModel):
    category: str
    balance: Decimal


class NetWorthBreakdownHistoryPointRead(BaseModel):
    as_of_date: date
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    asset_categories: list[CategoryBalanceRead]
    liability_categories: list[CategoryBalanceRead]


class NetWorthBreakdownHistoryRead(BaseModel):
    household_id: UUID
    points: list[NetWorthBreakdownHistoryPointRead]
