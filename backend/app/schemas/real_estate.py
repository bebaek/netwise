from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RealEstatePropertyCreate(BaseModel):
    account_id: UUID
    property_type: str = "residence"
    purchase_date: date | None = None
    purchase_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    down_payment: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    expected_appreciation_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    property_tax_annual: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    insurance_annual: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    maintenance_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    hoa_monthly: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class RealEstatePropertyRead(BaseModel):
    id: UUID
    household_id: UUID
    account_id: UUID
    property_type: str
    purchase_date: date | None
    purchase_price: Decimal | None
    down_payment: Decimal | None
    expected_appreciation_rate: Decimal | None
    property_tax_annual: Decimal | None
    insurance_annual: Decimal | None
    maintenance_rate: Decimal | None
    hoa_monthly: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MortgageProfileCreate(BaseModel):
    liability_account_id: UUID
    property_account_id: UUID | None = None
    original_principal: Decimal = Field(max_digits=18, decimal_places=2)
    interest_rate: Decimal = Field(max_digits=8, decimal_places=6)
    term_months: int
    start_date: date
    monthly_payment: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    rate_type: str = "fixed"


class MortgageProfileRead(BaseModel):
    id: UUID
    household_id: UUID
    liability_account_id: UUID
    property_account_id: UUID | None
    original_principal: Decimal
    interest_rate: Decimal
    term_months: int
    start_date: date
    monthly_payment: Decimal | None
    rate_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
