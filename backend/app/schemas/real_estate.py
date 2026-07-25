from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RealEstatePropertyCreate(BaseModel):
    account_id: UUID
    property_type: str = "residence"
    purchase_date: date | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    adjusted_tax_basis: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    down_payment: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    expected_appreciation_rate: Decimal | None = Field(
        default=Decimal("0.000000"), max_digits=8, decimal_places=6
    )
    property_tax_annual: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    insurance_annual: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    tax_and_insurance_annual: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    maintenance_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    hoa_monthly: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_rental: bool = False
    rental_start_date: date | None = None
    monthly_market_rent: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    other_monthly_income: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    rent_growth_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    vacancy_rate: Decimal | None = Field(default=None, ge=0, lt=1, max_digits=8, decimal_places=6)
    management_fee_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    utilities_annual: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    other_operating_expense_annual: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    capital_reserve_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    rental_deposit_account_id: UUID | None = None


class RealEstatePropertyUpdate(BaseModel):
    property_type: str | None = None
    purchase_date: date | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    adjusted_tax_basis: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    down_payment: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    expected_appreciation_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    property_tax_annual: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    insurance_annual: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    tax_and_insurance_annual: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    maintenance_rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=6)
    hoa_monthly: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_rental: bool | None = None
    rental_start_date: date | None = None
    monthly_market_rent: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    other_monthly_income: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    rent_growth_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    vacancy_rate: Decimal | None = Field(default=None, ge=0, lt=1, max_digits=8, decimal_places=6)
    management_fee_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    utilities_annual: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    other_operating_expense_annual: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    capital_reserve_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    rental_deposit_account_id: UUID | None = None


class RealEstatePropertyRead(BaseModel):
    id: UUID
    household_id: UUID
    account_id: UUID
    property_type: str
    purchase_date: date | None
    purchase_price: Decimal | None
    adjusted_tax_basis: Decimal | None
    down_payment: Decimal | None
    expected_appreciation_rate: Decimal | None
    property_tax_annual: Decimal | None
    insurance_annual: Decimal | None
    tax_and_insurance_annual: Decimal | None
    maintenance_rate: Decimal | None
    hoa_monthly: Decimal | None
    is_rental: bool
    rental_start_date: date | None
    monthly_market_rent: Decimal | None
    other_monthly_income: Decimal | None
    rent_growth_rate: Decimal | None
    vacancy_rate: Decimal | None
    management_fee_rate: Decimal | None
    utilities_annual: Decimal | None
    other_operating_expense_annual: Decimal | None
    capital_reserve_rate: Decimal | None
    rental_deposit_account_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RealEstateValuationPoint(BaseModel):
    as_of_date: date
    value: Decimal


class RealEstateAnalyticsRead(BaseModel):
    property_id: UUID
    account_id: UUID
    property_name: str
    valuation_date: date | None
    current_value: Decimal | None
    purchase_date: date | None
    purchase_price: Decimal | None
    expected_appreciation_rate: Decimal | None
    appreciation_amount: Decimal | None
    appreciation_rate: Decimal | None
    annualized_appreciation_rate: Decimal | None
    mortgage_balance: Decimal | None
    mortgage_balance_estimated: bool
    equity: Decimal | None
    estimated_annual_rental_income: Decimal | None
    estimated_noi: Decimal | None
    estimated_annual_cash_flow: Decimal | None
    gross_rental_yield: Decimal | None
    cap_rate: Decimal | None
    cash_on_cash_return: Decimal | None
    valuation_history: list[RealEstateValuationPoint]
    limitations: list[str]


class RealEstateSaleCreate(BaseModel):
    property_account_id: UUID
    sale_date: date
    gross_sale_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    proceeds_account_id: UUID | None = None
    selling_expense_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    estimated_tax_rate: Decimal = Field(
        default=Decimal("0.150000"), ge=0, lt=1, max_digits=8, decimal_places=6
    )


class RealEstateSaleRead(BaseModel):
    id: UUID
    household_id: UUID
    scenario_id: UUID
    property_account_id: UUID
    sale_date: date
    gross_sale_price: Decimal
    proceeds_account_id: UUID
    selling_expense_rate: Decimal | None
    estimated_tax_rate: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RealEstateLiquidationStrategyUpsert(BaseModel):
    enabled: bool = True
    optimization_mode: Literal["liquidity_shortfall", "maximize_liquid_runway"] = (
        "liquidity_shortfall"
    )
    priority: int = Field(default=100, ge=0)
    earliest_sale_date: date | None = None
    proceeds_account_id: UUID | None = None
    selling_expense_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    estimated_tax_rate: Decimal = Field(
        default=Decimal("0.150000"), ge=0, lt=1, max_digits=8, decimal_places=6
    )


class RealEstateLiquidationStrategyRead(BaseModel):
    id: UUID
    household_id: UUID
    scenario_id: UUID
    property_account_id: UUID
    enabled: bool
    optimization_mode: str
    priority: int
    earliest_sale_date: date | None
    proceeds_account_id: UUID
    selling_expense_rate: Decimal | None
    estimated_tax_rate: Decimal
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
