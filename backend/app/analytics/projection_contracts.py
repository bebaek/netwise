from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class ProjectionAccount:
    """Immutable account values required by the deterministic engine."""

    id: UUID
    name: str
    account_kind: str
    category: str
    liquidity_class: str
    retirement_tax_treatment: str | None
    expected_annual_yield: Decimal | None
    liquidation_expense_rate: Decimal | None


@dataclass(frozen=True)
class ProjectionEvent:
    account_id: UUID
    event_date: date
    amount: Decimal
    event_type: str


@dataclass(frozen=True)
class ProjectionIncomeSource:
    amount: Decimal
    frequency: str
    start_date: date
    end_date: date | None
    growth_rate: Decimal | None
    deposit_account_id: UUID | None


@dataclass(frozen=True)
class ProjectionTransferInput:
    from_account_id: UUID
    to_account_id: UUID
    annual_amount: Decimal
    start_date: date
    end_date: date | None
    growth_rate: Decimal | None


@dataclass(frozen=True)
class ProjectionSpendingItem:
    name: str
    category: str
    annual_amount: Decimal
    retirement_annual_amount: Decimal | None
    growth_rate: Decimal | None


@dataclass(frozen=True)
class ProjectionSettingsInput:
    annual_spending: Decimal | None
    spending_mode: str
    spending_inflation_rate: Decimal | None
    retirement_date: date | None
    retirement_annual_spending: Decimal | None
    spending_account_id: UUID | None
    tax_account_id: UUID | None


@dataclass(frozen=True)
class ProjectionMortgage:
    liability_account_id: UUID
    property_account_id: UUID | None
    original_principal: Decimal
    interest_rate: Decimal
    term_months: int
    start_date: date
    monthly_payment: Decimal | None


@dataclass(frozen=True)
class ProjectionProperty:
    account_id: UUID
    purchase_date: date | None
    purchase_price: Decimal | None
    adjusted_tax_basis: Decimal | None
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


@dataclass(frozen=True)
class ProjectionPropertySale:
    property_account_id: UUID
    sale_date: date
    gross_sale_price: Decimal
    proceeds_account_id: UUID
    selling_expense_rate: Decimal | None
    estimated_tax_rate: Decimal


@dataclass(frozen=True)
class ProjectionLiquidationStrategy:
    property_account_id: UUID
    enabled: bool
    optimization_mode: str
    priority: int
    earliest_sale_date: date | None
    proceeds_account_id: UUID
    selling_expense_rate: Decimal | None
    estimated_tax_rate: Decimal
