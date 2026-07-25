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
