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


class NetWorthHistoryRead(BaseModel):
    household_id: UUID
    points: list[NetWorthHistoryPointRead]
