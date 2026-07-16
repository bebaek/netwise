from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import AccountEventType, AccountKind, ProjectionBehavior, SnapshotSource


class AccountCreate(BaseModel):
    household_id: UUID
    name: str
    institution_name: str | None = None
    account_kind: AccountKind
    category: str
    liquidity_class: str
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountRead(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    institution_name: str | None
    account_kind: str
    category: str
    liquidity_class: str
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BalanceSnapshotCreate(BaseModel):
    as_of_date: date
    balance: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    source: SnapshotSource = SnapshotSource.manual
    confidence_level: str | None = None


class BalanceSnapshotRead(BaseModel):
    id: UUID
    household_id: UUID
    account_id: UUID
    as_of_date: date
    balance: Decimal
    currency: str
    source: str
    confidence_level: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountEventCreate(BaseModel):
    event_date: date
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    event_type: AccountEventType
    description: str | None = None
    projection_behavior: ProjectionBehavior = ProjectionBehavior.historical_only
    scenario_id: UUID | None = None


class AccountEventRead(BaseModel):
    id: UUID
    household_id: UUID
    account_id: UUID
    event_date: date
    amount: Decimal
    currency: str
    event_type: str
    description: str | None
    projection_behavior: str
    scenario_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
