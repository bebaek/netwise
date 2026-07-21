from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import (
    IncomeFrequency,
    SocialSecurityCalculationMode,
    SocialSecurityEarningsPattern,
)


class HouseholdPersonCreate(BaseModel):
    household_id: UUID
    name: str = Field(min_length=1, max_length=200)
    date_of_birth: date


class HouseholdPersonRead(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    date_of_birth: date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SocialSecurityEstimateCreate(BaseModel):
    household_id: UUID
    person_id: UUID
    calculation_mode: SocialSecurityCalculationMode
    claiming_date: date
    current_covered_earnings: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    completed_work_years: int | None = Field(default=None, ge=0, le=50)
    expected_work_end_date: date | None = None
    earnings_pattern: SocialSecurityEarningsPattern | None = None
    manual_monthly_benefit: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    cola_rate: Decimal = Field(default=Decimal("0.025"), ge=0, le=0.2, decimal_places=6)
    deposit_account_id: UUID | None = None


class SocialSecurityEstimateUpdate(SocialSecurityEstimateCreate):
    pass


class SocialSecurityEstimateRead(BaseModel):
    id: UUID
    household_id: UUID
    person_id: UUID
    income_source_id: UUID
    calculation_mode: str
    claiming_date: date
    current_covered_earnings: Decimal | None
    completed_work_years: int | None
    expected_work_end_date: date | None
    earnings_pattern: str | None
    manual_monthly_benefit: Decimal | None
    cola_rate: Decimal
    estimated_monthly_benefit: Decimal
    lower_monthly_benefit: Decimal
    upper_monthly_benefit: Decimal
    full_retirement_age_months: int
    benefit_at_full_retirement_age: Decimal
    calculation_version: str
    law_assumption_year: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


class ProjectionTransferCreate(BaseModel):
    household_id: UUID
    name: str = Field(min_length=1, max_length=200)
    from_account_id: UUID
    to_account_id: UUID
    annual_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    start_date: date
    end_date: date | None = None
    growth_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)


class ProjectionTransferRead(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    from_account_id: UUID
    to_account_id: UUID
    annual_amount: Decimal
    start_date: date
    end_date: date | None
    growth_rate: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpendingItemCreate(BaseModel):
    household_id: UUID
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="other", min_length=1, max_length=64)
    annual_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    retirement_annual_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    growth_rate: Decimal | None = Field(default=None, ge=-1, max_digits=8, decimal_places=6)


class SpendingItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    annual_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    retirement_annual_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    growth_rate: Decimal | None = Field(default=None, ge=-1, max_digits=8, decimal_places=6)


class SpendingItemRead(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    category: str
    annual_amount: Decimal
    retirement_annual_amount: Decimal | None
    growth_rate: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectionSettingsUpsert(BaseModel):
    annual_spending: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    spending_mode: Literal["manual", "itemized"] = "manual"
    spending_inflation_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    retirement_date: date | None = None
    retirement_annual_spending: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=2
    )
    spending_account_id: UUID | None = None
    tax_account_id: UUID | None = None


class ProjectionSettingsRead(BaseModel):
    id: UUID
    household_id: UUID
    annual_spending: Decimal | None
    spending_mode: str
    spending_inflation_rate: Decimal | None
    retirement_date: date | None
    retirement_annual_spending: Decimal | None
    spending_account_id: UUID | None
    tax_account_id: UUID | None
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
