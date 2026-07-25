from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class ProjectionAccountResult:
    account_id: UUID
    name: str
    account_kind: str
    category: str
    liquidity_class: str
    projected_balance: Decimal


@dataclass(frozen=True)
class ProjectionCashFlowResult:
    account_id: UUID
    account_name: str
    cash_flow_type: str
    amount: Decimal


@dataclass(frozen=True)
class ProjectionSpendingItemResult:
    name: str
    category: str
    amount: Decimal


@dataclass(frozen=True)
class ProjectionPointResult:
    year: int
    as_of_date: date
    net_worth: Decimal
    assets_total: Decimal
    liabilities_total: Decimal
    projected_income: Decimal
    projected_rental_income: Decimal
    projected_rental_expenses: Decimal
    projected_taxes: Decimal
    projected_spending: Decimal
    projected_owner_property_spending: Decimal
    projected_mortgage_spending: Decimal
    projected_spending_breakdown: tuple[ProjectionSpendingItemResult, ...]
    projected_liquidation_expenses: Decimal
    projected_unfunded_cash_flow: Decimal
    net_cash_flow: Decimal
    retirement_phase: bool
    cash_flows: tuple[ProjectionCashFlowResult, ...]
    accounts: tuple[ProjectionAccountResult, ...]


@dataclass(frozen=True)
class PropertySaleOptimizationSelectionResult:
    property_account_id: UUID
    property_name: str
    sale_date: date | None


@dataclass(frozen=True)
class PropertySaleOptimizationResult:
    mode: str
    candidate_month: int
    candidate_day: int
    schedules_evaluated: int
    first_retirement_withdrawal_date: date | None
    selected_sales: tuple[PropertySaleOptimizationSelectionResult, ...]


@dataclass(frozen=True)
class ProjectionResult:
    household_id: UUID
    start_year: int
    end_year: int
    interval: str
    spending_mode: str
    retirement_date: date | None
    first_retirement_withdrawal_date: date | None
    first_unfunded_date: date | None
    warnings: tuple[str, ...]
    points: tuple[ProjectionPointResult, ...]
    property_sale_optimization: PropertySaleOptimizationResult | None = None


def format_projection_result(result: ProjectionResult) -> dict:
    """Translate the simulation result into the stable API response shape."""
    response = {
        "household_id": result.household_id,
        "start_year": result.start_year,
        "end_year": result.end_year,
        "interval": result.interval,
        "spending_mode": result.spending_mode,
        "retirement_date": result.retirement_date,
        "first_retirement_withdrawal_date": result.first_retirement_withdrawal_date,
        "first_unfunded_date": result.first_unfunded_date,
        "warnings": list(result.warnings),
        "points": [_format_point(point) for point in result.points],
    }
    if result.property_sale_optimization is not None:
        response["property_sale_optimization"] = _format_property_sale_optimization(
            result.property_sale_optimization
        )
    return response


def _format_point(point: ProjectionPointResult) -> dict:
    return {
        "year": point.year,
        "as_of_date": point.as_of_date,
        "net_worth": point.net_worth,
        "assets_total": point.assets_total,
        "liabilities_total": point.liabilities_total,
        "projected_income": point.projected_income,
        "projected_rental_income": point.projected_rental_income,
        "projected_rental_expenses": point.projected_rental_expenses,
        "projected_taxes": point.projected_taxes,
        "projected_spending": point.projected_spending,
        "projected_owner_property_spending": point.projected_owner_property_spending,
        "projected_mortgage_spending": point.projected_mortgage_spending,
        "projected_spending_breakdown": [
            {
                "name": item.name,
                "category": item.category,
                "amount": item.amount,
            }
            for item in point.projected_spending_breakdown
        ],
        "projected_liquidation_expenses": point.projected_liquidation_expenses,
        "projected_unfunded_cash_flow": point.projected_unfunded_cash_flow,
        "net_cash_flow": point.net_cash_flow,
        "retirement_phase": point.retirement_phase,
        "cash_flows": [
            {
                "account_id": cash_flow.account_id,
                "account_name": cash_flow.account_name,
                "cash_flow_type": cash_flow.cash_flow_type,
                "amount": cash_flow.amount,
            }
            for cash_flow in point.cash_flows
        ],
        "accounts": [
            {
                "account_id": account.account_id,
                "name": account.name,
                "account_kind": account.account_kind,
                "category": account.category,
                "liquidity_class": account.liquidity_class,
                "projected_balance": account.projected_balance,
            }
            for account in point.accounts
        ],
    }


def _format_property_sale_optimization(
    optimization: PropertySaleOptimizationResult,
) -> dict:
    return {
        "mode": optimization.mode,
        "candidate_month": optimization.candidate_month,
        "candidate_day": optimization.candidate_day,
        "schedules_evaluated": optimization.schedules_evaluated,
        "first_retirement_withdrawal_date": optimization.first_retirement_withdrawal_date,
        "selected_sales": [
            {
                "property_account_id": selection.property_account_id,
                "property_name": selection.property_name,
                "sale_date": selection.sale_date,
            }
            for selection in optimization.selected_sales
        ],
    }
