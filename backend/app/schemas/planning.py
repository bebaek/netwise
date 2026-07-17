from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import IncomeFrequency


class IncomeSourceCreate(BaseModel):
    household_id: UUID
    name: str
    income_type: str = "other"
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    frequency: IncomeFrequency
    start_date: date
    end_date: date | None = None
    growth_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    deposit_account_id: UUID | None = None


class IncomeSourceRead(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    income_type: str
    amount: Decimal
    currency: str
    frequency: str
    start_date: date
    end_date: date | None
    growth_rate: Decimal | None
    deposit_account_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnnualTaxRecordCreate(BaseModel):
    household_id: UUID
    tax_year: int
    gross_income: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    total_taxes_paid: Decimal = Field(max_digits=18, decimal_places=2)
    refund_or_amount_due: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    notes: str | None = None


class AnnualTaxRecordRead(BaseModel):
    id: UUID
    household_id: UUID
    tax_year: int
    gross_income: Decimal | None
    total_taxes_paid: Decimal
    refund_or_amount_due: Decimal | None
    effective_tax_rate: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
