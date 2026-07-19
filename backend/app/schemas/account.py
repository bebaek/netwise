from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import (
    AccountEventType,
    AccountKind,
    ProjectionBehavior,
    RetirementTaxTreatment,
    SnapshotSource,
)


class AccountCreate(BaseModel):
    household_id: UUID
    name: str
    institution_name: str | None = None
    account_kind: AccountKind
    category: str
    liquidity_class: str
    retirement_tax_treatment: RetirementTaxTreatment | None = None
    expected_annual_yield: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    liquidation_expense_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    cost_basis: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountUpdate(BaseModel):
    name: str | None = None
    institution_name: str | None = None
    account_kind: AccountKind | None = None
    category: str | None = None
    liquidity_class: str | None = None
    retirement_tax_treatment: RetirementTaxTreatment | None = None
    expected_annual_yield: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    liquidation_expense_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    cost_basis: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


class AccountRead(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    institution_name: str | None
    account_kind: str
    category: str
    liquidity_class: str
    retirement_tax_treatment: str | None
    expected_annual_yield: Decimal | None
    liquidation_expense_rate: Decimal | None
    cost_basis: Decimal | None
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


class BalanceSnapshotUpdate(BaseModel):
    as_of_date: date | None = None
    balance: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    source: SnapshotSource | None = None
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


class HouseholdBalanceSnapshotRead(BalanceSnapshotRead):
    account_name: str
    account_kind: str
    account_category: str


class BalanceSnapshotBatchItemCreate(BaseModel):
    account_id: UUID
    balance: Decimal = Field(max_digits=18, decimal_places=2)


class BalanceSnapshotBatchCreate(BaseModel):
    as_of_date: date
    currency: str = Field(default="USD", min_length=3, max_length=3)
    source: SnapshotSource = SnapshotSource.manual
    confidence_level: str | None = None
    snapshots: list[BalanceSnapshotBatchItemCreate] = Field(min_length=1)


class BalanceSnapshotBatchRead(BaseModel):
    household_id: UUID
    as_of_date: date
    created_count: int
    updated_count: int
    snapshots: list[BalanceSnapshotRead]


class AccountEventCreate(BaseModel):
    event_date: date
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    event_type: AccountEventType
    description: str | None = None
    projection_behavior: ProjectionBehavior = ProjectionBehavior.historical_only
    scenario_id: UUID | None = None


class AccountEventUpdate(BaseModel):
    account_id: UUID | None = None
    event_date: date | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    event_type: AccountEventType | None = None
    description: str | None = None
    projection_behavior: ProjectionBehavior | None = None
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
