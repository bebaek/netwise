from dataclasses import dataclass
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
