from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.mortgage import estimate_mortgage_balance
from app.analytics.projection_input import ProjectionInput, load_projection_input
from app.db.models import (
    Account,
    AccountEvent,
    AccountEventType,
    AccountKind,
    IncomeFrequency,
    IncomeSource,
    MortgageProfile,
    ProjectionTransfer,
    RealEstateLiquidationStrategy,
    RealEstateProperty,
    RealEstateSale,
    RetirementTaxTreatment,
    SpendingItem,
)

DEFAULT_CATEGORY_YIELDS = {
    "cash": Decimal("0.010000"),
    "checking": Decimal("0.010000"),
    "savings": Decimal("0.020000"),
    "taxable_investment": Decimal("0.050000"),
    "brokerage": Decimal("0.050000"),
    "retirement": Decimal("0.050000"),
    "real_estate": Decimal("0.030000"),
    "mortgage": Decimal("0.000000"),
    "credit_card": Decimal("0.000000"),
}
DEFAULT_SPENDING_INFLATION_RATE = Decimal("0.030000")
DEFAULT_INCOME_GROWTH_RATE = Decimal("0.020000")
DEFAULT_CAPITAL_GAINS_TAX_RATE = Decimal("0.150000")
TAXABLE_INVESTMENT_CATEGORIES = {"taxable_investment", "brokerage"}


def _current_date() -> date:
    return date.today()


DEFAULT_LIQUIDATION_EXPENSE_RATES = {
    "taxable_investment": Decimal("0.010000"),
    "brokerage": Decimal("0.010000"),
    "real_estate": Decimal("0.060000"),
}


@dataclass
class WithdrawalResult:
    net_amount: Decimal = Decimal("0.00")
    taxable_amount: Decimal = Decimal("0.00")
    capital_gains_tax: Decimal = Decimal("0.00")
    liquidation_expenses: Decimal = Decimal("0.00")
    explicit_taxes: Decimal = Decimal("0.00")
    unfunded_amount: Decimal = Decimal("0.00")

    def add(self, other: "WithdrawalResult") -> None:
        self.net_amount = (self.net_amount + other.net_amount).quantize(Decimal("0.01"))
        self.taxable_amount = (self.taxable_amount + other.taxable_amount).quantize(Decimal("0.01"))
        self.capital_gains_tax = (self.capital_gains_tax + other.capital_gains_tax).quantize(
            Decimal("0.01")
        )
        self.liquidation_expenses = (
            self.liquidation_expenses + other.liquidation_expenses
        ).quantize(Decimal("0.01"))
        self.explicit_taxes = (self.explicit_taxes + other.explicit_taxes).quantize(Decimal("0.01"))
        self.unfunded_amount = (self.unfunded_amount + other.unfunded_amount).quantize(
            Decimal("0.01")
        )


@dataclass
class ProjectedPropertySale:
    property_account_id: UUID
    gross_sale_price: Decimal
    proceeds_account_id: UUID
    selling_expense_rate: Decimal | None
    estimated_tax_rate: Decimal


@dataclass
class AutomaticPropertySaleContext:
    strategies: list[RealEstateLiquidationStrategy]
    fixed_sale_property_ids: set[UUID]
    mortgage_profiles_by_property: dict[UUID, MortgageProfile]
    property_profiles: dict[UUID, RealEstateProperty]
    sold_mortgage_account_ids: set[UUID]
    used_property_ids: set[UUID]
    as_of_date: date

    def next_strategy(
        self,
        accounts_by_id: dict[UUID, Account],
        balances: dict[UUID, Decimal],
    ) -> RealEstateLiquidationStrategy | None:
        eligible = [
            strategy
            for strategy in self.strategies
            if strategy.enabled
            and strategy.property_account_id not in self.fixed_sale_property_ids
            and strategy.property_account_id not in self.used_property_ids
            and (
                strategy.earliest_sale_date is None
                or strategy.earliest_sale_date <= self.as_of_date
            )
            and strategy.property_account_id in accounts_by_id
            and strategy.proceeds_account_id in accounts_by_id
            and balances[strategy.property_account_id] > Decimal("0.00")
        ]
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda strategy: (
                strategy.priority,
                accounts_by_id[strategy.property_account_id].name.lower(),
            ),
        )


CASH_FLOW_CATEGORY_PRIORITY = {
    "cash": 0,
    "checking": 0,
    "savings": 1,
    "taxable_investment": 2,
    "brokerage": 2,
    "retirement": 3,
}

BANK_CATEGORIES = {"cash", "checking", "savings"}
LIQUIDITY_CLASSES = {"cash", "liquid", "marketable", "retirement_liquid"}

# Default withdrawal sequence: checking, other cash, taxable investments, Roth
# retirement, then other retirement accounts. Remaining eligible liquid accounts
# are fallbacks.
DEFAULT_FUNDING_ACCOUNT_NAMES = {"checking"}


AccountEventOutflowTypes = {
    AccountEventType.withdrawal,
    AccountEventType.large_purchase,
    AccountEventType.tax_payment,
    AccountEventType.account_removed,
}
AccountEventInflowTypes = {
    AccountEventType.contribution,
    AccountEventType.asset_sale,
    AccountEventType.gift,
    AccountEventType.inheritance,
    AccountEventType.account_added,
}


def _validate_projection_request(start_year: int, end_year: int, interval: str) -> None:
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")
    if interval not in {"annual", "quarterly", "monthly"}:
        raise ValueError("interval must be one of: annual, quarterly, monthly")


def calculate_net_worth_projection(
    db: Session,
    household_id: UUID,
    *,
    start_year: int,
    end_year: int,
    annual_spending: Decimal | None = None,
    spending_inflation_rate: Decimal | None = None,
    spending_account_id: UUID | None = None,
    tax_account_id: UUID | None = None,
    interval: str = "annual",
) -> dict:
    """Compatibility adapter that loads persisted input before projection."""
    _validate_projection_request(start_year, end_year, interval)
    projection_input = load_projection_input(
        db,
        household_id,
        start_date=date(start_year, 1, 1),
        end_date=date(end_year, 12, 31),
    )
    return calculate_projection_from_input(
        projection_input,
        start_year=start_year,
        end_year=end_year,
        annual_spending=annual_spending,
        spending_inflation_rate=spending_inflation_rate,
        spending_account_id=spending_account_id,
        tax_account_id=tax_account_id,
        interval=interval,
    )


def calculate_projection_from_input(
    projection_input: ProjectionInput,
    *,
    start_year: int,
    end_year: int,
    annual_spending: Decimal | None = None,
    spending_inflation_rate: Decimal | None = None,
    spending_account_id: UUID | None = None,
    tax_account_id: UUID | None = None,
    interval: str = "annual",
    _scheduled_sales: dict[UUID, date | None] | None = None,
    _skip_optimization: bool = False,
) -> dict:
    """Run the deterministic projection without database access."""
    _validate_projection_request(start_year, end_year, interval)
    household_id = projection_input.household_id
    projection_date = _current_date()
    accounts = projection_input.accounts
    initial_balances = projection_input.initial_balances
    mortgage_profiles = projection_input.mortgage_profiles
    property_profiles = projection_input.property_profiles
    real_estate_sales = projection_input.real_estate_sales
    automatic_sale_strategies = projection_input.automatic_sale_strategies
    projection_events = projection_input.projection_events
    income_sources = projection_input.income_sources
    projection_transfers = projection_input.projection_transfers
    spending_items = projection_input.spending_items
    projection_settings = projection_input.projection_settings
    tax_rate = projection_input.tax_rate
    cost_bases = projection_input.cost_bases
    cost_basis_estimates = projection_input.cost_basis_estimates

    balances = dict(initial_balances)
    # Cost basis is only tracked for taxable investment accounts and must be
    # copied because the optimizer reuses ProjectionInput across candidate runs.
    basis_balances = dict(cost_bases)
    mortgage_profiles_by_property = {
        profile.property_account_id: profile
        for profile in mortgage_profiles.values()
        if profile.property_account_id is not None
    }
    owner_occupied_properties = [
        profile for profile in property_profiles.values() if not profile.is_rental
    ]
    owner_occupied_property_ids = {profile.account_id for profile in owner_occupied_properties}
    owner_occupied_mortgages = [
        profile
        for profile in mortgage_profiles.values()
        if profile.property_account_id in owner_occupied_property_ids
    ]
    effective_annual_spending = (
        annual_spending
        if annual_spending is not None
        else projection_settings.annual_spending
        if projection_settings is not None
        else None
    )
    effective_spending_inflation_rate = (
        spending_inflation_rate
        if spending_inflation_rate is not None
        else projection_settings.spending_inflation_rate
        if projection_settings is not None
        and projection_settings.spending_inflation_rate is not None
        else DEFAULT_SPENDING_INFLATION_RATE
    )
    effective_spending_account_id = (
        spending_account_id
        if spending_account_id is not None
        else projection_settings.spending_account_id
        if projection_settings is not None
        else None
    )
    effective_tax_account_id = (
        tax_account_id
        if tax_account_id is not None
        else projection_settings.tax_account_id
        if projection_settings is not None
        else None
    )
    effective_retirement_date = (
        projection_settings.retirement_date if projection_settings is not None else None
    )
    effective_retirement_annual_spending = (
        projection_settings.retirement_annual_spending
        if projection_settings is not None
        and projection_settings.retirement_annual_spending is not None
        else effective_annual_spending
    )
    retirement_spending_baseline = (
        (start_year, effective_retirement_annual_spending.quantize(Decimal("0.01")))
        if effective_retirement_date is not None
        and effective_retirement_annual_spending is not None
        else None
    )
    accounts_by_id = {account.id: account for account in accounts}
    _validate_cash_flow_account(accounts_by_id, effective_spending_account_id, "Spending account")
    _validate_cash_flow_account(accounts_by_id, effective_tax_account_id, "Tax account")
    for income_source in income_sources:
        _validate_cash_flow_account(
            accounts_by_id, income_source.deposit_account_id, "Income deposit account"
        )
    spending_baseline = (
        (start_year, effective_annual_spending.quantize(Decimal("0.01")))
        if effective_annual_spending is not None
        else None
    )
    configured_spending_mode = (
        projection_settings.spending_mode if projection_settings is not None else "manual"
    )
    use_itemized_spending = annual_spending is None and (
        configured_spending_mode == "itemized"
        or (effective_annual_spending is None and bool(spending_items))
    )
    if _scheduled_sales is None and not _skip_optimization:
        optimization_strategies = [
            strategy
            for strategy in automatic_sale_strategies
            if strategy.enabled and strategy.optimization_mode == "maximize_liquid_runway"
        ]
        if optimization_strategies:
            return _optimize_liquid_runway_sales(
                start_year=start_year,
                end_year=end_year,
                annual_spending=annual_spending,
                spending_inflation_rate=spending_inflation_rate,
                spending_account_id=spending_account_id,
                tax_account_id=tax_account_id,
                interval=interval,
                projection_input=projection_input,
                strategies=optimization_strategies,
            )

    points = []
    months_per_period = {"annual": 12, "quarterly": 3, "monthly": 1}[interval]
    period_ends = [
        date(year, month, monthrange(year, month)[1])
        for year in range(start_year, end_year + 1)
        for month in range(months_per_period, 13, months_per_period)
    ]
    sold_mortgage_account_ids: set[UUID] = set()
    automatically_sold_property_ids: set[UUID] = set()
    scheduled_sales = _scheduled_sales or {}
    optimized_property_ids = {
        strategy.property_account_id
        for strategy in automatic_sale_strategies
        if strategy.enabled and strategy.optimization_mode == "maximize_liquid_runway"
    }
    fixed_sale_property_ids = {
        sale.property_account_id for sale in real_estate_sales
    } | optimized_property_ids
    for as_of_date in period_ends:
        year = as_of_date.year
        period_start = date(year, as_of_date.month - months_per_period + 1, 1)

        for account in accounts:
            if account.id in mortgage_profiles:
                if account.id in sold_mortgage_account_ids:
                    balances[account.id] = Decimal("0.00")
                    continue
                balances[account.id] = estimate_mortgage_balance(
                    mortgage_profiles[account.id], as_of_date
                )
                continue

            annual_yield = _yield_for_account(account, property_profiles.get(account.id))
            period_yield = (
                annual_yield
                if months_per_period == 12
                else (Decimal("1") + annual_yield) ** (Decimal(months_per_period) / Decimal("12"))
                - Decimal("1")
            )
            balances[account.id] = (balances[account.id] * (Decimal("1") + period_yield)).quantize(
                Decimal("0.01")
            )

        cash_flows = []
        withdrawal_result = WithdrawalResult()
        automatic_sale_context = AutomaticPropertySaleContext(
            strategies=automatic_sale_strategies,
            fixed_sale_property_ids=fixed_sale_property_ids,
            mortgage_profiles_by_property=mortgage_profiles_by_property,
            property_profiles=property_profiles,
            sold_mortgage_account_ids=sold_mortgage_account_ids,
            used_property_ids=automatically_sold_property_ids,
            as_of_date=as_of_date,
        )
        year_operations = (
            [
                (sale.sale_date, 0, sale)
                for sale in real_estate_sales
                if period_start <= sale.sale_date <= as_of_date
            ]
            + [
                (scheduled_date, 1, strategy)
                for strategy in automatic_sale_strategies
                if (scheduled_date := scheduled_sales.get(strategy.property_account_id)) is not None
                and period_start <= scheduled_date <= as_of_date
            ]
            + [
                (event.event_date, 2, event)
                for event in projection_events
                if period_start <= event.event_date <= as_of_date
            ]
        )
        for _, operation_kind, operation in sorted(
            year_operations, key=lambda item: (item[0], item[1])
        ):
            if operation_kind == 0:
                withdrawal_result.add(
                    _apply_real_estate_sale(
                        accounts,
                        accounts_by_id,
                        balances,
                        cash_flows,
                        operation,
                        property_profiles.get(operation.property_account_id),
                        mortgage_profiles_by_property.get(operation.property_account_id),
                        sold_mortgage_account_ids,
                        tax_rate,
                        basis_balances,
                    )
                )
            elif operation_kind == 1:
                projected_sale = ProjectedPropertySale(
                    property_account_id=operation.property_account_id,
                    gross_sale_price=balances[operation.property_account_id],
                    proceeds_account_id=operation.proceeds_account_id,
                    selling_expense_rate=operation.selling_expense_rate,
                    estimated_tax_rate=operation.estimated_tax_rate,
                )
                withdrawal_result.add(
                    _apply_real_estate_sale(
                        accounts,
                        accounts_by_id,
                        balances,
                        cash_flows,
                        projected_sale,
                        property_profiles.get(operation.property_account_id),
                        mortgage_profiles_by_property.get(operation.property_account_id),
                        sold_mortgage_account_ids,
                        tax_rate,
                        basis_balances,
                    )
                )
            else:
                withdrawal_result.add(
                    _apply_projection_event(
                        accounts_by_id,
                        balances,
                        cash_flows,
                        operation,
                        tax_rate,
                        automatic_sale_context,
                        basis_balances,
                    )
                )

        projected_income = Decimal("0.00")
        projected_rental_income = Decimal("0.00")
        projected_rental_expenses = Decimal("0.00")
        for property_profile in property_profiles.values():
            rental_income, rental_expenses, rental_withdrawal_result = _apply_rental_cash_flow(
                property_profile,
                accounts,
                accounts_by_id,
                balances,
                cash_flows,
                period_start,
                as_of_date,
                tax_rate,
                automatic_sale_context,
                basis_balances,
            )
            withdrawal_result.add(rental_withdrawal_result)
            rental_mortgage_debt_service, mortgage_withdrawal_result = (
                _apply_rental_mortgage_debt_service(
                    property_profile,
                    mortgage_profiles_by_property.get(property_profile.account_id),
                    accounts,
                    accounts_by_id,
                    balances,
                    cash_flows,
                    period_start,
                    as_of_date,
                    sold_mortgage_account_ids,
                    tax_rate,
                    automatic_sale_context,
                    basis_balances,
                )
            )
            withdrawal_result.add(mortgage_withdrawal_result)
            projected_rental_income += rental_income
            projected_rental_expenses += rental_expenses + rental_mortgage_debt_service
        for income_source in income_sources:
            income_amount = _projected_income_source_for_period(
                income_source, period_start, as_of_date, months_per_period
            )
            projected_income += income_amount
            if income_amount != Decimal("0.00"):
                target_account = _cash_flow_target_account(
                    accounts, accounts_by_id, income_source.deposit_account_id
                )
                if target_account is not None:
                    _apply_account_cash_flow(
                        balances, cash_flows, target_account, "income", income_amount
                    )

        projected_income = projected_income.quantize(Decimal("0.01"))
        projected_rental_income = projected_rental_income.quantize(Decimal("0.01"))
        projected_rental_expenses = projected_rental_expenses.quantize(Decimal("0.01"))
        taxable_income = max(
            projected_income + projected_rental_income - projected_rental_expenses, Decimal("0.00")
        )
        income_taxes = (taxable_income * tax_rate).quantize(Decimal("0.01"))
        if use_itemized_spending:
            projected_spending_breakdown = _projected_spending_items_for_period(
                spending_items,
                effective_retirement_date,
                start_year,
                period_start,
                as_of_date,
                months_per_period,
                effective_spending_inflation_rate,
            )
            projected_non_mortgage_spending = sum(
                (item["amount"] for item in projected_spending_breakdown),
                Decimal("0.00"),
            ).quantize(Decimal("0.01"))
        else:
            projected_non_mortgage_spending = _projected_spending_for_period(
                spending_baseline,
                retirement_spending_baseline,
                effective_retirement_date,
                period_start,
                as_of_date,
                months_per_period,
                effective_spending_inflation_rate,
            )
            projected_spending_breakdown = (
                [
                    {
                        "name": "Unitemized non-mortgage spending",
                        "category": "other",
                        "amount": projected_non_mortgage_spending,
                    }
                ]
                if projected_non_mortgage_spending != Decimal("0.00")
                else []
            )
        projected_owner_property_spending_breakdown = _projected_owner_property_spending_for_period(
            owner_occupied_properties,
            accounts_by_id,
            balances,
            start_year,
            period_start,
            as_of_date,
            months_per_period,
            effective_spending_inflation_rate,
        )
        projected_owner_property_spending = sum(
            (item["amount"] for item in projected_owner_property_spending_breakdown),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        projected_spending_breakdown.extend(projected_owner_property_spending_breakdown)
        projected_mortgage_spending = _projected_owner_mortgage_spending_for_period(
            owner_occupied_mortgages,
            period_start,
            as_of_date,
            sold_mortgage_account_ids,
        )
        if projected_mortgage_spending != Decimal("0.00"):
            projected_spending_breakdown.append(
                {
                    "name": "Owner-occupied mortgage",
                    "category": "housing",
                    "amount": projected_mortgage_spending,
                }
            )
        projected_spending = (
            projected_non_mortgage_spending
            + projected_owner_property_spending
            + projected_mortgage_spending
        ).quantize(Decimal("0.01"))
        for spending_amount, cash_flow_type in (
            (projected_non_mortgage_spending, "spending"),
            (projected_owner_property_spending, "owner_property_spending"),
            (projected_mortgage_spending, "mortgage_spending"),
        ):
            if spending_amount == Decimal("0.00"):
                continue
            withdrawal_result.add(
                _withdraw_from_assets(
                    accounts,
                    accounts_by_id,
                    balances,
                    cash_flows,
                    spending_amount,
                    cash_flow_type,
                    effective_spending_account_id,
                    tax_rate,
                    automatic_sale_context,
                    basis_balances,
                )
            )
        ordinary_taxable = (withdrawal_result.taxable_amount * tax_rate).quantize(Decimal("0.01"))
        withdrawal_taxes = (ordinary_taxable + withdrawal_result.capital_gains_tax).quantize(
            Decimal("0.01")
        )
        projected_taxes = (
            income_taxes + withdrawal_taxes + withdrawal_result.explicit_taxes
        ).quantize(Decimal("0.01"))
        projected_liquidation_expenses = withdrawal_result.liquidation_expenses
        projected_unfunded_cash_flow = withdrawal_result.unfunded_amount
        if income_taxes != Decimal("0.00"):
            tax_payment_result = _withdraw_from_assets(
                accounts,
                accounts_by_id,
                balances,
                cash_flows,
                income_taxes,
                "tax_payment",
                effective_tax_account_id,
                tax_rate,
                automatic_sale_context,
                basis_balances,
            )
            projected_taxes = (
                projected_taxes
                + (tax_payment_result.taxable_amount * tax_rate)
                + tax_payment_result.capital_gains_tax
                + tax_payment_result.explicit_taxes
            ).quantize(Decimal("0.01"))
            projected_liquidation_expenses = (
                projected_liquidation_expenses + tax_payment_result.liquidation_expenses
            ).quantize(Decimal("0.01"))
            projected_unfunded_cash_flow = (
                projected_unfunded_cash_flow + tax_payment_result.unfunded_amount
            ).quantize(Decimal("0.01"))

        for projection_transfer in projection_transfers:
            planned_transfer = _projected_transfer_for_period(
                projection_transfer, period_start, as_of_date
            )
            source_account = accounts_by_id.get(projection_transfer.from_account_id)
            destination_account = accounts_by_id.get(projection_transfer.to_account_id)
            if (
                planned_transfer <= Decimal("0.00")
                or source_account is None
                or destination_account is None
            ):
                continue
            transfer_amount = min(
                planned_transfer, max(balances[source_account.id], Decimal("0.00"))
            )
            if transfer_amount <= Decimal("0.00"):
                continue
            if source_account.category in TAXABLE_INVESTMENT_CATEGORIES and (
                destination_account.category not in TAXABLE_INVESTMENT_CATEGORIES
            ):
                available = max(balances[source_account.id] + transfer_amount, Decimal("0.00"))
                if available > Decimal("0.00"):
                    gain_fraction = (
                        max(
                            available
                            - max(
                                basis_balances.get(source_account.id, Decimal("0.00")),
                                Decimal("0.00"),
                            ),
                            Decimal("0.00"),
                        )
                        / available
                    )
                    basis_balances[source_account.id] = max(
                        basis_balances.get(source_account.id, Decimal("0.00"))
                        - (transfer_amount * (Decimal("1.00") - gain_fraction)),
                        Decimal("0.00"),
                    ).quantize(Decimal("0.01"))
            elif (
                source_account.category not in TAXABLE_INVESTMENT_CATEGORIES
                and destination_account.category in TAXABLE_INVESTMENT_CATEGORIES
            ):
                basis_balances[destination_account.id] = (
                    basis_balances.get(destination_account.id, Decimal("0.00")) + transfer_amount
                ).quantize(Decimal("0.01"))
            _apply_account_cash_flow(
                balances,
                cash_flows,
                source_account,
                "recurring_transfer_out",
                -transfer_amount,
            )
            _apply_account_cash_flow(
                balances,
                cash_flows,
                destination_account,
                "recurring_transfer_in",
                transfer_amount,
            )

        net_cash_flow = (
            projected_income
            + projected_rental_income
            - projected_rental_expenses
            - projected_taxes
            - projected_spending
            - projected_liquidation_expenses
        ).quantize(Decimal("0.01"))

        if as_of_date <= projection_date:
            continue

        account_points = [
            {
                "account_id": account.id,
                "name": account.name,
                "account_kind": account.account_kind,
                "category": account.category,
                "liquidity_class": account.liquidity_class,
                "projected_balance": balances[account.id],
            }
            for account in accounts
        ]
        assets_total = sum(
            (
                balances[account.id]
                for account in accounts
                if account.account_kind == AccountKind.asset
            ),
            Decimal("0.00"),
        )
        liabilities_total = sum(
            (
                balances[account.id]
                for account in accounts
                if account.account_kind == AccountKind.liability
            ),
            Decimal("0.00"),
        )
        points.append(
            {
                "year": year,
                "as_of_date": as_of_date,
                "net_worth": assets_total - liabilities_total,
                "assets_total": assets_total,
                "liabilities_total": liabilities_total,
                "projected_income": projected_income,
                "projected_rental_income": projected_rental_income,
                "projected_rental_expenses": projected_rental_expenses,
                "projected_taxes": projected_taxes,
                "projected_spending": projected_spending,
                "projected_owner_property_spending": projected_owner_property_spending,
                "projected_mortgage_spending": projected_mortgage_spending,
                "projected_spending_breakdown": projected_spending_breakdown,
                "projected_liquidation_expenses": projected_liquidation_expenses,
                "projected_unfunded_cash_flow": projected_unfunded_cash_flow,
                "net_cash_flow": net_cash_flow,
                "retirement_phase": (
                    effective_retirement_date is not None
                    and effective_retirement_date <= as_of_date
                ),
                "cash_flows": cash_flows,
                "accounts": account_points,
            }
        )

    warnings = _property_sale_tax_basis_warnings(
        accounts_by_id,
        property_profiles,
        real_estate_sales,
        automatic_sale_strategies,
    )
    if use_itemized_spending and not spending_items:
        warnings.insert(
            0,
            "Itemized spending mode has no spending items; projected non-mortgage spending is $0.00.",
        )
    taxable_account_ids = {
        account.id for account in accounts if account.category in TAXABLE_INVESTMENT_CATEGORIES
    }
    if any(account_id in taxable_account_ids for account_id in cost_basis_estimates):
        estimate_names = sorted(
            accounts_by_id[account_id].name
            for account_id in cost_basis_estimates
            if account_id in taxable_account_ids and account_id in accounts_by_id
        )
        if estimate_names:
            warnings.append(
                "Taxable investment cost basis estimated from oldest balance snapshots for: "
                + ", ".join(estimate_names)
                + ". Enter an explicit cost basis on each account for more accurate capital gains taxes."
            )
    result = {
        "household_id": household_id,
        "start_year": start_year,
        "end_year": end_year,
        "interval": interval,
        "spending_mode": "itemized" if use_itemized_spending else "manual",
        "retirement_date": effective_retirement_date,
        "warnings": warnings,
        "points": points,
    }
    result["first_retirement_withdrawal_date"] = _first_retirement_withdrawal_date(result, accounts)
    result["first_unfunded_date"] = next(
        (
            point["as_of_date"]
            for point in points
            if point["projected_unfunded_cash_flow"] > Decimal("0.00")
        ),
        None,
    )
    return result


def _optimize_liquid_runway_sales(
    *,
    start_year: int,
    end_year: int,
    annual_spending: Decimal | None,
    spending_inflation_rate: Decimal | None,
    spending_account_id: UUID | None,
    tax_account_id: UUID | None,
    interval: str,
    projection_input: ProjectionInput,
    strategies: list[RealEstateLiquidationStrategy],
) -> dict:
    """Choose ordered March 1 property sales that delay retirement withdrawals longest."""
    ordered_strategies = sorted(
        strategies,
        key=lambda strategy: (
            strategy.priority,
            next(
                account.name.lower()
                for account in projection_input.accounts
                if account.id == strategy.property_account_id
            ),
        ),
    )
    best_result: dict | None = None
    best_score: tuple[int, int, Decimal, Decimal] | None = None
    best_schedule: dict[UUID, date | None] = {}
    schedules_evaluated = 0
    evaluated_schedules: set[tuple[date | None, ...]] = set()

    def evaluate(schedule: dict[UUID, date | None]) -> None:
        nonlocal best_result, best_score, best_schedule, schedules_evaluated
        schedule_key = tuple(
            schedule[strategy.property_account_id] for strategy in ordered_strategies
        )
        if schedule_key in evaluated_schedules:
            return
        evaluated_schedules.add(schedule_key)
        result = calculate_projection_from_input(
            projection_input,
            start_year=start_year,
            end_year=end_year,
            annual_spending=annual_spending,
            spending_inflation_rate=spending_inflation_rate,
            spending_account_id=spending_account_id,
            tax_account_id=tax_account_id,
            interval=interval,
            _scheduled_sales=schedule,
            _skip_optimization=True,
        )
        schedules_evaluated += 1
        score = _liquid_runway_score(result, projection_input.accounts)
        if best_score is None or score > best_score:
            best_result = result
            best_score = score
            best_schedule = dict(schedule)

    never_schedule = {strategy.property_account_id: None for strategy in ordered_strategies}
    evaluate(never_schedule)
    if best_result is None:
        raise ValueError("Unable to evaluate property sale schedules")

    first_retirement_date = _first_retirement_withdrawal_date(
        best_result, projection_input.accounts
    )
    candidate_end_year = first_retirement_date.year if first_retirement_date else end_year
    while True:
        for schedule in _ordered_march_sale_schedules(
            ordered_strategies,
            start_year=start_year,
            end_year=candidate_end_year,
            not_before=max(date(start_year, 1, 1), _current_date()),
        ):
            evaluate(schedule)

        if best_result is None:
            raise ValueError("Unable to evaluate property sale schedules")
        expanded_retirement_date = _first_retirement_withdrawal_date(
            best_result, projection_input.accounts
        )
        expanded_end_year = expanded_retirement_date.year if expanded_retirement_date else end_year
        if expanded_end_year <= candidate_end_year or candidate_end_year == end_year:
            break
        candidate_end_year = min(expanded_end_year, end_year)

    accounts_by_id = {account.id: account for account in projection_input.accounts}
    first_retirement_date = _first_retirement_withdrawal_date(
        best_result, projection_input.accounts
    )
    best_result["property_sale_optimization"] = {
        "mode": "maximize_liquid_runway",
        "candidate_month": 3,
        "candidate_day": 1,
        "schedules_evaluated": schedules_evaluated,
        "first_retirement_withdrawal_date": first_retirement_date,
        "selected_sales": [
            {
                "property_account_id": strategy.property_account_id,
                "property_name": accounts_by_id[strategy.property_account_id].name,
                "sale_date": best_schedule[strategy.property_account_id],
            }
            for strategy in ordered_strategies
        ],
    }
    return best_result


def _ordered_march_sale_schedules(
    strategies: list[RealEstateLiquidationStrategy],
    *,
    start_year: int,
    end_year: int,
    not_before: date,
) -> list[dict[UUID, date | None]]:
    schedules: list[dict[UUID, date | None]] = []

    def build(
        index: int,
        previous_date: date | None,
        previous_was_never: bool,
        schedule: dict[UUID, date | None],
    ) -> None:
        if index == len(strategies):
            schedules.append(dict(schedule))
            return
        strategy = strategies[index]
        if previous_was_never:
            choices: list[date | None] = [None]
        else:
            choices = [
                date(year, 3, 1)
                for year in range(start_year, end_year + 1)
                if date(year, 3, 1) >= not_before
                and (
                    strategy.earliest_sale_date is None
                    or date(year, 3, 1) >= strategy.earliest_sale_date
                )
                and (previous_date is None or date(year, 3, 1) >= previous_date)
            ]
            choices.append(None)
        for choice in choices:
            schedule[strategy.property_account_id] = choice
            build(index + 1, choice, choice is None, schedule)
        schedule.pop(strategy.property_account_id, None)

    build(0, None, False, {})
    return schedules


def _liquid_runway_score(
    result: dict,
    accounts: list[Account],
) -> tuple[int, int, Decimal, Decimal]:
    points = result["points"]
    retirement_ids = {account.id for account in accounts if account.category == "retirement"}
    retirement_index = len(points) + 1
    for index, point in enumerate(points):
        if any(
            cash_flow["account_id"] in retirement_ids and cash_flow["amount"] < Decimal("0.00")
            for cash_flow in point["cash_flows"]
        ):
            retirement_index = index
            break

    unfunded_index = len(points) + 1
    for index, point in enumerate(points):
        if point["projected_unfunded_cash_flow"] > Decimal("0.00"):
            unfunded_index = index
            break

    balance_point_index = min(max(retirement_index - 1, 0), len(points) - 1)
    liquid_account_ids = {
        account.id
        for account in accounts
        if account.account_kind == AccountKind.asset
        and account.category != "retirement"
        and account.liquidity_class in LIQUIDITY_CLASSES
    }
    liquid_balance = sum(
        (
            account_point["projected_balance"]
            for account_point in points[balance_point_index]["accounts"]
            if account_point["account_id"] in liquid_account_ids
        ),
        Decimal("0.00"),
    )
    return (
        retirement_index,
        unfunded_index,
        liquid_balance,
        points[-1]["net_worth"],
    )


def _first_retirement_withdrawal_date(
    result: dict,
    accounts: list[Account],
) -> date | None:
    retirement_ids = {account.id for account in accounts if account.category == "retirement"}
    for point in result["points"]:
        if any(
            cash_flow["account_id"] in retirement_ids and cash_flow["amount"] < Decimal("0.00")
            for cash_flow in point["cash_flows"]
        ):
            return point["as_of_date"]
    return None


def _projected_transfer_for_period(
    transfer: ProjectionTransfer,
    period_start: date,
    period_end: date,
) -> Decimal:
    active_start = max(period_start, transfer.start_date)
    active_end = min(period_end, transfer.end_date or period_end)
    if active_start > active_end:
        return Decimal("0.00")
    active_months = (
        (active_end.year - active_start.year) * 12 + active_end.month - active_start.month + 1
    )
    growth_rate = transfer.growth_rate or Decimal("0.00")
    years_elapsed = max(period_start.year - transfer.start_date.year, 0)
    annual_amount = transfer.annual_amount * ((Decimal("1.00") + growth_rate) ** years_elapsed)
    return (annual_amount * Decimal(active_months) / Decimal("12")).quantize(Decimal("0.01"))


def _projected_spending_items_for_period(
    spending_items: list[SpendingItem],
    retirement_date: date | None,
    baseline_year: int,
    period_start: date,
    period_end: date,
    months_per_period: int,
    default_growth_rate: Decimal,
) -> list[dict]:
    """Project each spending item independently and preserve its category breakdown."""
    breakdown = []
    for item in spending_items:
        growth_rate = item.growth_rate if item.growth_rate is not None else default_growth_rate
        retirement_amount = (
            item.retirement_annual_amount
            if item.retirement_annual_amount is not None
            else item.annual_amount
        )
        amount = _projected_spending_for_period(
            (baseline_year, item.annual_amount),
            (baseline_year, retirement_amount) if retirement_date is not None else None,
            retirement_date,
            period_start,
            period_end,
            months_per_period,
            growth_rate,
        )
        breakdown.append(
            {
                "name": item.name,
                "category": item.category,
                "amount": amount,
            }
        )
    return breakdown


def _projected_owner_property_spending_for_period(
    property_profiles: list[RealEstateProperty],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    start_year: int,
    period_start: date,
    period_end: date,
    months_per_period: int,
    spending_inflation_rate: Decimal,
) -> list[dict]:
    """Return inflation-adjusted owner property tax and insurance spending.

    Property-level costs are spread evenly across active months. A combined tax
    and insurance amount takes precedence over the separate fields, matching the
    rental expense treatment. Costs stop when the property is sold.
    """
    years_elapsed = max(period_start.year - start_year, 0)
    inflation_factor = (Decimal("1") + spending_inflation_rate) ** years_elapsed
    breakdown: list[dict] = []
    for profile in property_profiles:
        account = accounts_by_id.get(profile.account_id)
        if account is None or balances.get(profile.account_id, Decimal("0.00")) <= Decimal("0.00"):
            continue
        active_months = min(
            _active_months_in_period(profile.purchase_date, period_start, period_end),
            months_per_period,
        )
        if active_months == 0:
            continue
        period_fraction = Decimal(active_months) / Decimal("12")
        if profile.tax_and_insurance_annual is not None:
            costs = [("property tax and insurance", profile.tax_and_insurance_annual)]
        else:
            costs = [
                ("property tax", profile.property_tax_annual or Decimal("0.00")),
                ("homeowners insurance", profile.insurance_annual or Decimal("0.00")),
            ]
        for label, annual_amount in costs:
            amount = (annual_amount * inflation_factor * period_fraction).quantize(Decimal("0.01"))
            if amount == Decimal("0.00"):
                continue
            breakdown.append(
                {
                    "name": f"{account.name} {label}",
                    "category": "housing",
                    "amount": amount,
                }
            )
    return breakdown


def _projected_owner_mortgage_spending_for_period(
    mortgage_profiles: list[MortgageProfile],
    period_start: date,
    period_end: date,
    sold_mortgage_account_ids: set[UUID],
) -> Decimal:
    """Return fixed owner-occupied mortgage payments due during the period.

    Mortgage payments are modeled separately from inflation-adjusted household
    spending. They stop after the final scheduled payment or a property sale.
    """
    spending = Decimal("0.00")
    for profile in mortgage_profiles:
        if profile.liability_account_id in sold_mortgage_account_ids:
            continue
        active_months = _scheduled_mortgage_payment_months(profile, period_start, period_end)
        if active_months == 0:
            continue
        monthly_payment = profile.monthly_payment or _amortized_monthly_payment(profile)
        spending += monthly_payment * Decimal(active_months)
    return spending.quantize(Decimal("0.01"))


def _scheduled_mortgage_payment_months(
    profile: MortgageProfile,
    period_start: date,
    period_end: date,
) -> int:
    """Count scheduled payment months overlapping an inclusive projection period."""
    period_start_month = period_start.year * 12 + period_start.month - 1
    period_end_month = period_end.year * 12 + period_end.month - 1
    origination_month = profile.start_date.year * 12 + profile.start_date.month - 1
    first_payment_month = origination_month + 1
    final_payment_month = origination_month + profile.term_months
    active_start = max(period_start_month, first_payment_month)
    active_end = min(period_end_month, final_payment_month)
    return max(active_end - active_start + 1, 0)


def _projected_spending_for_period(
    spending_baseline: tuple[int, Decimal] | None,
    retirement_spending_baseline: tuple[int, Decimal] | None,
    retirement_date: date | None,
    period_start: date,
    period_end: date,
    months_per_period: int,
    spending_inflation_rate: Decimal,
) -> Decimal:
    """Return inflation-adjusted spending, blending a retirement transition period."""
    working_annual_spending = _projected_spending_for_year(
        spending_baseline, period_start.year, spending_inflation_rate
    )
    retirement_annual_spending = _projected_spending_for_year(
        retirement_spending_baseline, period_start.year, spending_inflation_rate
    )
    period_fraction = Decimal(months_per_period) / Decimal("12")

    if retirement_date is None or retirement_spending_baseline is None:
        return (working_annual_spending * period_fraction).quantize(Decimal("0.01"))
    if retirement_date <= period_start:
        return (retirement_annual_spending * period_fraction).quantize(Decimal("0.01"))
    if retirement_date > period_end:
        return (working_annual_spending * period_fraction).quantize(Decimal("0.01"))

    period_days = Decimal((period_end - period_start).days + 1)
    retirement_days = Decimal((period_end - retirement_date).days + 1)
    working_days = period_days - retirement_days
    blended_annual_spending = (
        (working_annual_spending * working_days) + (retirement_annual_spending * retirement_days)
    ) / period_days
    return (blended_annual_spending * period_fraction).quantize(Decimal("0.01"))


def _projected_spending_for_year(
    spending_baseline: tuple[int, Decimal] | None,
    year: int,
    spending_inflation_rate: Decimal,
) -> Decimal:
    if spending_baseline is None:
        return Decimal("0.00")
    baseline_year, baseline_amount = spending_baseline
    years_elapsed = max(year - baseline_year, 0)
    return (baseline_amount * ((Decimal("1") + spending_inflation_rate) ** years_elapsed)).quantize(
        Decimal("0.01")
    )


def _projected_income_for_year(income_sources: list[IncomeSource], year: int) -> Decimal:
    return sum(
        (_projected_income_source_for_year(source, year) for source in income_sources),
        Decimal("0.00"),
    )


def _projected_income_source_for_period(
    source: IncomeSource,
    period_start: date,
    period_end: date,
    months_per_period: int,
) -> Decimal:
    """Allocate an active income source across a monthly, quarterly, or annual period.

    The first fine-grained projection release spreads the source's annualized amount
    evenly over its active periods.  A later payroll scheduler can replace this for
    weekly and biweekly sources without changing the projection API.
    """
    if source.start_date > period_end or (
        source.end_date is not None and source.end_date < period_start
    ):
        return Decimal("0.00")
    annual_amount = _projected_income_source_for_year(source, period_start.year)
    active_start = max(source.start_date, period_start)
    active_end = min(source.end_date, period_end) if source.end_date is not None else period_end
    active_months = (
        (active_end.year - active_start.year) * 12 + active_end.month - active_start.month + 1
    )
    return (annual_amount * Decimal(active_months) / Decimal("12")).quantize(Decimal("0.01"))


def _projected_income_source_for_year(source: IncomeSource, year: int) -> Decimal:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    if source.start_date > year_end or (
        source.end_date is not None and source.end_date < year_start
    ):
        return Decimal("0.00")

    annual_amount = _annualize_income(source.amount, source.frequency)
    growth_rate = (
        source.growth_rate if source.growth_rate is not None else DEFAULT_INCOME_GROWTH_RATE
    )
    years_elapsed = max(year - source.start_date.year, 0)
    return (annual_amount * ((Decimal("1") + growth_rate) ** years_elapsed)).quantize(
        Decimal("0.01")
    )


def _annualize_income(amount: Decimal, frequency: str) -> Decimal:
    multipliers = {
        IncomeFrequency.weekly: Decimal("52"),
        IncomeFrequency.biweekly: Decimal("26"),
        IncomeFrequency.semimonthly: Decimal("24"),
        IncomeFrequency.monthly: Decimal("12"),
        IncomeFrequency.quarterly: Decimal("4"),
        IncomeFrequency.annually: Decimal("1"),
    }
    return amount * multipliers.get(frequency, Decimal("1"))


def _validate_cash_flow_account(
    accounts_by_id: dict[UUID, Account], account_id: UUID | None, label: str
) -> None:
    if account_id is None:
        return
    account = accounts_by_id.get(account_id)
    if account is None or account.account_kind != AccountKind.asset:
        raise ValueError(f"{label} must be an active asset account in the household")


def _cash_flow_target_account(
    accounts: list[Account], accounts_by_id: dict[UUID, Account], account_id: UUID | None
) -> Account | None:
    if account_id is not None:
        return accounts_by_id[account_id]
    asset_accounts = [account for account in accounts if account.account_kind == AccountKind.asset]
    if not asset_accounts:
        return None
    return min(asset_accounts, key=_cash_flow_priority)


def _active_months_in_period(
    rental_start_date: date | None, period_start: date, period_end: date
) -> int:
    """Count active rental months in a period, including a partial starting month."""
    if rental_start_date is None or rental_start_date <= period_start:
        first_active_month = period_start
    elif rental_start_date > period_end:
        return 0
    else:
        first_active_month = rental_start_date
    return (
        (period_end.year - first_active_month.year) * 12
        + period_end.month
        - first_active_month.month
        + 1
    )


def _apply_rental_cash_flow(
    property_profile: RealEstateProperty,
    accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    period_start: date,
    period_end: date,
    tax_rate: Decimal,
    automatic_sale_context: AutomaticPropertySaleContext | None = None,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> tuple[Decimal, Decimal, WithdrawalResult]:
    """Apply non-debt rental operating cash flow and return income, expenses, and funding."""
    property_account = accounts_by_id.get(property_profile.account_id)
    active_months = _active_months_in_period(
        property_profile.rental_start_date, period_start, period_end
    )
    if (
        not property_profile.is_rental
        or property_account is None
        or balances[property_account.id] <= Decimal("0.00")
        or active_months == 0
    ):
        return Decimal("0.00"), Decimal("0.00"), WithdrawalResult()

    years_elapsed = max(
        period_start.year - (property_profile.rental_start_date or period_start).year, 0
    )
    rent_growth = property_profile.rent_growth_rate or Decimal("0.00")
    monthly_rent = (property_profile.monthly_market_rent or Decimal("0.00")) * (
        (Decimal("1") + rent_growth) ** years_elapsed
    )
    scheduled_rent = monthly_rent * Decimal(active_months)
    effective_rent = scheduled_rent * (
        Decimal("1") - (property_profile.vacancy_rate or Decimal("0.00"))
    )
    other_income = (property_profile.other_monthly_income or Decimal("0.00")) * Decimal(
        active_months
    )
    income = (effective_rent + other_income).quantize(Decimal("0.01"))
    annual_prorate = Decimal(active_months) / Decimal("12")
    expenses = (
        (
            property_profile.tax_and_insurance_annual
            if property_profile.tax_and_insurance_annual is not None
            else (property_profile.property_tax_annual or Decimal("0.00"))
            + (property_profile.insurance_annual or Decimal("0.00"))
        )
        * annual_prorate
        + (property_profile.utilities_annual or Decimal("0.00")) * annual_prorate
        + (property_profile.other_operating_expense_annual or Decimal("0.00")) * annual_prorate
        + (property_profile.hoa_monthly or Decimal("0.00")) * Decimal(active_months)
        + balances[property_account.id]
        * (
            (property_profile.maintenance_rate or Decimal("0.00"))
            + (property_profile.capital_reserve_rate or Decimal("0.00"))
        )
        * annual_prorate
        + effective_rent * (property_profile.management_fee_rate or Decimal("0.00"))
    ).quantize(Decimal("0.01"))
    deposit_account = accounts_by_id.get(property_profile.rental_deposit_account_id)
    if deposit_account is None:
        deposit_account = _cash_flow_target_account(accounts, accounts_by_id, None)
    if deposit_account is not None and income != Decimal("0.00"):
        _apply_account_cash_flow(balances, cash_flows, deposit_account, "rental_income", income)
    funding_result = WithdrawalResult()
    if expenses != Decimal("0.00"):
        funding_result = _withdraw_from_assets(
            accounts,
            accounts_by_id,
            balances,
            cash_flows,
            expenses,
            "rental_expense",
            deposit_account.id if deposit_account is not None else None,
            tax_rate,
            automatic_sale_context,
            basis_balances,
        )
    return income, expenses, funding_result


def _apply_rental_mortgage_debt_service(
    property_profile: RealEstateProperty,
    mortgage_profile: MortgageProfile | None,
    accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    period_start: date,
    period_end: date,
    sold_mortgage_account_ids: set[UUID],
    tax_rate: Decimal,
    automatic_sale_context: AutomaticPropertySaleContext | None = None,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> tuple[Decimal, WithdrawalResult]:
    """Deduct a linked rental's scheduled mortgage payment from rental cash flow.

    Only rentals are included. A property sale marks its linked mortgage as paid off,
    so future periods automatically stop this debt-service outflow.
    """
    if not property_profile.is_rental or mortgage_profile is None:
        return Decimal("0.00"), WithdrawalResult()
    if mortgage_profile.liability_account_id in sold_mortgage_account_ids:
        return Decimal("0.00"), WithdrawalResult()
    property_account = accounts_by_id.get(property_profile.account_id)
    mortgage_account = accounts_by_id.get(mortgage_profile.liability_account_id)
    active_months = _active_months_in_period(
        property_profile.rental_start_date, period_start, period_end
    )
    if (
        property_account is None
        or mortgage_account is None
        or balances[property_account.id] <= Decimal("0.00")
        or balances[mortgage_account.id] <= Decimal("0.00")
        or mortgage_profile.start_date > period_end
        or active_months == 0
    ):
        return Decimal("0.00"), WithdrawalResult()

    monthly_payment = mortgage_profile.monthly_payment or _amortized_monthly_payment(
        mortgage_profile
    )
    debt_service = (monthly_payment * Decimal(active_months)).quantize(Decimal("0.01"))
    if debt_service <= Decimal("0.00"):
        return Decimal("0.00"), WithdrawalResult()
    deposit_account = accounts_by_id.get(property_profile.rental_deposit_account_id)
    if deposit_account is None:
        deposit_account = _cash_flow_target_account(accounts, accounts_by_id, None)
    funding_result = _withdraw_from_assets(
        accounts,
        accounts_by_id,
        balances,
        cash_flows,
        debt_service,
        "rental_mortgage_debt_service",
        deposit_account.id if deposit_account is not None else None,
        tax_rate,
        automatic_sale_context,
        basis_balances,
    )
    return debt_service, funding_result


def _amortized_monthly_payment(profile: MortgageProfile) -> Decimal:
    monthly_rate = profile.interest_rate / Decimal("12")
    if monthly_rate == Decimal("0.00"):
        return (profile.original_principal / Decimal(profile.term_months)).quantize(Decimal("0.01"))
    factor = (Decimal("1") + monthly_rate) ** profile.term_months
    return (profile.original_principal * monthly_rate * factor / (factor - Decimal("1"))).quantize(
        Decimal("0.01")
    )


def _apply_account_cash_flow(
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    account: Account,
    cash_flow_type: str,
    amount: Decimal,
) -> None:
    amount = amount.quantize(Decimal("0.01"))
    projected_balance = (balances[account.id] + amount).quantize(Decimal("0.01"))
    if projected_balance < Decimal("0.00"):
        raise ValueError(f"Projection cash flow would make account '{account.name}' negative")
    balances[account.id] = projected_balance
    cash_flows.append(
        {
            "account_id": account.id,
            "account_name": account.name,
            "cash_flow_type": cash_flow_type,
            "amount": amount,
        }
    )


def _property_sale_tax_basis_warnings(
    accounts_by_id: dict[UUID, Account],
    property_profiles: dict[UUID, RealEstateProperty],
    real_estate_sales: list[RealEstateSale],
    automatic_sale_strategies: list[RealEstateLiquidationStrategy],
) -> list[str]:
    property_ids = {
        sale.property_account_id
        for sale in real_estate_sales
        if sale.estimated_tax_rate > Decimal("0.00")
    } | {
        strategy.property_account_id
        for strategy in automatic_sale_strategies
        if strategy.enabled and strategy.estimated_tax_rate > Decimal("0.00")
    }
    warnings = []
    for property_id in sorted(
        property_ids,
        key=lambda item: (
            accounts_by_id[item].name.casefold() if item in accounts_by_id else str(item)
        ),
    ):
        account = accounts_by_id.get(property_id)
        profile = property_profiles.get(property_id)
        property_name = account.name if account is not None else str(property_id)
        if profile is None or (
            profile.adjusted_tax_basis is None and profile.purchase_price is None
        ):
            warnings.append(
                f"{property_name}: sale tax uses the gross-price fallback because tax basis is missing."
            )
        elif profile.adjusted_tax_basis is None:
            warnings.append(
                f"{property_name}: sale tax uses purchase price as basis; enter adjusted tax basis "
                "to reflect improvements and depreciation."
            )
    return warnings


def _apply_real_estate_sale(
    accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    sale: RealEstateSale | ProjectedPropertySale,
    property_profile: RealEstateProperty | None,
    mortgage_profile: MortgageProfile | None,
    sold_mortgage_account_ids: set[UUID],
    tax_rate: Decimal,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> WithdrawalResult:
    property_account = accounts_by_id.get(sale.property_account_id)
    proceeds_account = accounts_by_id.get(sale.proceeds_account_id)
    if property_account is None or proceeds_account is None:
        raise ValueError("Property sale accounts must be active accounts in the household")

    automatic_sale = isinstance(sale, ProjectedPropertySale)
    cash_flow_prefix = "automatic_property_sale" if automatic_sale else "property_sale"
    property_balance = max(balances[property_account.id], Decimal("0.00"))
    if property_balance != Decimal("0.00"):
        _apply_account_cash_flow(
            balances,
            cash_flows,
            property_account,
            f"{cash_flow_prefix}_removal",
            -property_balance,
        )

    mortgage_payoff = Decimal("0.00")
    if mortgage_profile is not None:
        mortgage_account = accounts_by_id.get(mortgage_profile.liability_account_id)
        if mortgage_account is not None:
            mortgage_payoff = max(balances[mortgage_account.id], Decimal("0.00"))
            if mortgage_payoff != Decimal("0.00"):
                _apply_account_cash_flow(
                    balances, cash_flows, mortgage_account, "mortgage_payoff", -mortgage_payoff
                )
            sold_mortgage_account_ids.add(mortgage_account.id)

    selling_expense_rate = (
        sale.selling_expense_rate
        if sale.selling_expense_rate is not None
        else _liquidation_expense_rate(property_account)
    )
    selling_expense = (sale.gross_sale_price * selling_expense_rate).quantize(Decimal("0.01"))
    if selling_expense != Decimal("0.00"):
        cash_flows.append(
            {
                "account_id": property_account.id,
                "account_name": property_account.name,
                "cash_flow_type": f"{cash_flow_prefix}_expense",
                "amount": -selling_expense,
            }
        )

    tax_basis = (
        property_profile.adjusted_tax_basis
        if property_profile is not None and property_profile.adjusted_tax_basis is not None
        else property_profile.purchase_price
        if property_profile is not None
        else None
    )
    taxable_gain = (
        max(sale.gross_sale_price - selling_expense - tax_basis, Decimal("0.00"))
        if tax_basis is not None
        else sale.gross_sale_price
    )
    estimated_sale_tax = (taxable_gain * sale.estimated_tax_rate).quantize(Decimal("0.01"))
    if estimated_sale_tax != Decimal("0.00"):
        cash_flows.append(
            {
                "account_id": property_account.id,
                "account_name": property_account.name,
                "cash_flow_type": f"{cash_flow_prefix}_tax",
                "amount": -estimated_sale_tax,
            }
        )

    net_proceeds = (
        sale.gross_sale_price - mortgage_payoff - selling_expense - estimated_sale_tax
    ).quantize(Decimal("0.01"))
    if net_proceeds >= Decimal("0.00"):
        if net_proceeds != Decimal("0.00"):
            if (
                basis_balances is not None
                and proceeds_account.category in TAXABLE_INVESTMENT_CATEGORIES
            ):
                basis_balances[proceeds_account.id] = (
                    basis_balances.get(proceeds_account.id, Decimal("0.00")) + net_proceeds
                ).quantize(Decimal("0.01"))
            _apply_account_cash_flow(
                balances,
                cash_flows,
                proceeds_account,
                f"{cash_flow_prefix}_proceeds",
                net_proceeds,
            )
        return WithdrawalResult(
            liquidation_expenses=selling_expense,
            explicit_taxes=estimated_sale_tax,
        )

    shortfall_result = _withdraw_from_assets(
        [account for account in accounts if account.id != property_account.id],
        accounts_by_id,
        balances,
        cash_flows,
        abs(net_proceeds),
        "property_sale_shortfall",
        None,
        tax_rate,
        None,
        basis_balances,
    )
    shortfall_result.liquidation_expenses = (
        shortfall_result.liquidation_expenses + selling_expense
    ).quantize(Decimal("0.01"))
    shortfall_result.explicit_taxes = (
        shortfall_result.explicit_taxes + estimated_sale_tax
    ).quantize(Decimal("0.01"))
    return shortfall_result


def _apply_projection_event(
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    event: AccountEvent,
    tax_rate: Decimal,
    automatic_sale_context: AutomaticPropertySaleContext | None = None,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> WithdrawalResult:
    account = accounts_by_id.get(event.account_id)
    if account is None:
        return WithdrawalResult()

    amount = _projection_event_amount(event)
    if amount == Decimal("0.00"):
        return WithdrawalResult()

    if account.account_kind == AccountKind.asset and amount < Decimal("0.00"):
        return _withdraw_from_assets(
            list(accounts_by_id.values()),
            accounts_by_id,
            balances,
            cash_flows,
            abs(amount),
            event.event_type,
            event.account_id,
            tax_rate,
            automatic_sale_context,
            basis_balances,
        )

    if account.category in TAXABLE_INVESTMENT_CATEGORIES and basis_balances is not None:
        basis_balances[account.id] = (
            basis_balances.get(account.id, Decimal("0.00")) + amount
        ).quantize(Decimal("0.01"))
    _apply_account_cash_flow(balances, cash_flows, account, event.event_type, amount)
    return WithdrawalResult()


def _projection_event_amount(event: AccountEvent) -> Decimal:
    if event.event_type in AccountEventOutflowTypes:
        return -abs(event.amount)
    if event.event_type in AccountEventInflowTypes:
        return abs(event.amount)
    return event.amount


def _withdraw_from_assets(
    accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    amount: Decimal,
    cash_flow_type: str,
    preferred_account_id: UUID | None,
    tax_rate: Decimal,
    automatic_sale_context: AutomaticPropertySaleContext | None = None,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> WithdrawalResult:
    amount = amount.quantize(Decimal("0.01"))
    if automatic_sale_context is None:
        return _withdraw_from_account_pool(
            accounts,
            accounts_by_id,
            balances,
            cash_flows,
            amount,
            cash_flow_type,
            preferred_account_id,
            tax_rate,
            basis_balances,
        )

    result = WithdrawalResult()
    non_retirement_accounts = [account for account in accounts if account.category != "retirement"]
    non_retirement_preference = (
        preferred_account_id
        if any(account.id == preferred_account_id for account in non_retirement_accounts)
        else None
    )
    funding_attempt = _withdraw_from_account_pool(
        non_retirement_accounts,
        accounts_by_id,
        balances,
        cash_flows,
        amount,
        cash_flow_type,
        non_retirement_preference,
        tax_rate,
        basis_balances,
    )
    remaining = funding_attempt.unfunded_amount
    funding_attempt.unfunded_amount = Decimal("0.00")
    result.add(funding_attempt)
    additional_unfunded = Decimal("0.00")

    while remaining > Decimal("0.00"):
        strategy = automatic_sale_context.next_strategy(accounts_by_id, balances)
        if strategy is None:
            break
        automatic_sale_context.used_property_ids.add(strategy.property_account_id)
        projected_sale = ProjectedPropertySale(
            property_account_id=strategy.property_account_id,
            gross_sale_price=balances[strategy.property_account_id],
            proceeds_account_id=strategy.proceeds_account_id,
            selling_expense_rate=strategy.selling_expense_rate,
            estimated_tax_rate=strategy.estimated_tax_rate,
        )
        sale_result = _apply_real_estate_sale(
            accounts,
            accounts_by_id,
            balances,
            cash_flows,
            projected_sale,
            automatic_sale_context.property_profiles.get(strategy.property_account_id),
            automatic_sale_context.mortgage_profiles_by_property.get(strategy.property_account_id),
            automatic_sale_context.sold_mortgage_account_ids,
            tax_rate,
        )
        additional_unfunded += sale_result.unfunded_amount
        sale_result.unfunded_amount = Decimal("0.00")
        result.add(sale_result)

        funding_attempt = _withdraw_from_account_pool(
            non_retirement_accounts,
            accounts_by_id,
            balances,
            cash_flows,
            remaining,
            cash_flow_type,
            non_retirement_preference,
            tax_rate,
            basis_balances,
        )
        remaining = funding_attempt.unfunded_amount
        funding_attempt.unfunded_amount = Decimal("0.00")
        result.add(funding_attempt)

    if remaining > Decimal("0.00"):
        retirement_accounts = [account for account in accounts if account.category == "retirement"]
        retirement_preference = (
            preferred_account_id
            if any(account.id == preferred_account_id for account in retirement_accounts)
            else None
        )
        funding_attempt = _withdraw_from_account_pool(
            retirement_accounts,
            accounts_by_id,
            balances,
            cash_flows,
            remaining,
            cash_flow_type,
            retirement_preference,
            tax_rate,
            basis_balances,
        )
        remaining = funding_attempt.unfunded_amount
        funding_attempt.unfunded_amount = Decimal("0.00")
        result.add(funding_attempt)

    result.unfunded_amount = (additional_unfunded + remaining).quantize(Decimal("0.01"))
    return result


def _withdraw_from_account_pool(
    accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    amount: Decimal,
    cash_flow_type: str,
    preferred_account_id: UUID | None,
    tax_rate: Decimal,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> WithdrawalResult:
    remaining_net = amount.quantize(Decimal("0.01"))
    result = WithdrawalResult()
    if remaining_net == Decimal("0.00"):
        return result

    asset_accounts = [account for account in accounts if account.account_kind == AccountKind.asset]
    if not asset_accounts:
        result.unfunded_amount = remaining_net
        return result

    effective_preference = (
        preferred_account_id
        if any(account.id == preferred_account_id for account in asset_accounts)
        else None
    )
    ordered_accounts = _withdrawal_order(asset_accounts, accounts_by_id, effective_preference)
    for account in ordered_accounts:
        available = max(balances[account.id], Decimal("0.00"))
        if available == Decimal("0.00"):
            continue

        taxes_apply = _withdrawal_has_tax_consequences(account)
        has_basis_tracking = (
            basis_balances is not None
            and account.id in basis_balances
            and available > Decimal("0.00")
        )
        capital_gain_fraction = Decimal("0.00")
        if has_basis_tracking:
            effective_tax_rate = DEFAULT_CAPITAL_GAINS_TAX_RATE
            basis = max(basis_balances[account.id], Decimal("0.00"))
            capital_gain_fraction = max(available - basis, Decimal("0.00")) / available
        else:
            effective_tax_rate = tax_rate if taxes_apply else Decimal("0.00")
        liquidation_expense_rate = _liquidation_expense_rate(account)
        if has_basis_tracking:
            drag_rate = (effective_tax_rate * capital_gain_fraction) + liquidation_expense_rate
        else:
            drag_rate = effective_tax_rate + liquidation_expense_rate
        if drag_rate >= Decimal("1.00"):
            continue

        gross_needed = (remaining_net / (Decimal("1.00") - drag_rate)).quantize(
            Decimal("0.01"), rounding=ROUND_UP
        )
        gross_deduction = min(available, gross_needed)
        if gross_deduction == Decimal("0.00"):
            continue

        if has_basis_tracking:
            taxable_portion = (gross_deduction * capital_gain_fraction).quantize(Decimal("0.01"))
        else:
            taxable_portion = gross_deduction if taxes_apply else Decimal("0.00")
        tax_amount = (taxable_portion * effective_tax_rate).quantize(Decimal("0.01"))
        liquidation_expense = (gross_deduction * liquidation_expense_rate).quantize(Decimal("0.01"))
        net_amount = (gross_deduction - tax_amount - liquidation_expense).quantize(Decimal("0.01"))
        if net_amount == Decimal("0.00"):
            continue

        _apply_account_cash_flow(balances, cash_flows, account, cash_flow_type, -net_amount)
        if tax_amount != Decimal("0.00"):
            _apply_account_cash_flow(balances, cash_flows, account, "tax_payment", -tax_amount)
        if liquidation_expense != Decimal("0.00"):
            _apply_account_cash_flow(
                balances, cash_flows, account, "liquidation_expense", -liquidation_expense
            )
        if has_basis_tracking:
            basis_balances[account.id] = max(
                basis_balances[account.id]
                - (gross_deduction * (Decimal("1.00") - capital_gain_fraction)),
                Decimal("0.00"),
            ).quantize(Decimal("0.01"))

        result.net_amount = (result.net_amount + net_amount).quantize(Decimal("0.01"))
        if has_basis_tracking:
            result.capital_gains_tax = (result.capital_gains_tax + tax_amount).quantize(
                Decimal("0.01")
            )
        elif taxes_apply:
            result.taxable_amount = (result.taxable_amount + taxable_portion).quantize(
                Decimal("0.01")
            )
        result.liquidation_expenses = (result.liquidation_expenses + liquidation_expense).quantize(
            Decimal("0.01")
        )
        remaining_net = (remaining_net - net_amount).quantize(Decimal("0.01"))
        # Rounding gross withdrawals up can satisfy the requested net amount by
        # a cent. Treat that as fully funded instead of running a second,
        # negative withdrawal that creates compensating micro cash flows.
        if remaining_net <= Decimal("0.00"):
            return result

    result.unfunded_amount = remaining_net
    return result


def _withdrawal_has_tax_consequences(account: Account) -> bool:
    if account.category in {"cash", "checking", "savings"}:
        return False
    if (
        account.category == "retirement"
        and account.retirement_tax_treatment == RetirementTaxTreatment.roth
    ):
        return False
    return True


def _liquidation_expense_rate(account: Account) -> Decimal:
    if account.liquidation_expense_rate is not None:
        return account.liquidation_expense_rate
    return DEFAULT_LIQUIDATION_EXPENSE_RATES.get(account.category, Decimal("0.000000"))


def _funding_priority(account: Account) -> tuple[int, str] | None:
    account_name = account.name.casefold()
    if account_name in DEFAULT_FUNDING_ACCOUNT_NAMES:
        return (0, account_name)
    if account.category in BANK_CATEGORIES:
        return (1, account_name)
    if (
        account.category in {"taxable_investment", "brokerage"}
        and account.liquidity_class in LIQUIDITY_CLASSES
    ):
        return (2, account_name)
    if (
        account.category == "retirement"
        and account.retirement_tax_treatment == RetirementTaxTreatment.roth
    ):
        return (3, account_name)
    if account.category == "retirement" and account.liquidity_class in LIQUIDITY_CLASSES:
        return (4, account_name)
    if account.category != "real_estate" and account.liquidity_class in LIQUIDITY_CLASSES:
        return (5, account_name)
    return None


def _withdrawal_order(
    asset_accounts: list[Account],
    accounts_by_id: dict[UUID, Account],
    preferred_account_id: UUID | None,
) -> list[Account]:
    ordered_accounts = sorted(
        (account for account in asset_accounts if _funding_priority(account) is not None),
        key=_funding_priority,
    )
    if preferred_account_id is None:
        return ordered_accounts
    preferred_account = accounts_by_id[preferred_account_id]
    if _funding_priority(preferred_account) is None:
        return [preferred_account] + [
            account for account in ordered_accounts if account.id != preferred_account_id
        ]
    preferred_index = next(
        index
        for index, account in enumerate(ordered_accounts)
        if account.id == preferred_account_id
    )
    return ordered_accounts[preferred_index:]


def _cash_flow_priority(account: Account) -> tuple[int, str]:
    return (CASH_FLOW_CATEGORY_PRIORITY.get(account.category, 99), account.name)


def _yield_for_account(
    account: Account,
    property_profile: RealEstateProperty | None,
) -> Decimal:
    if account.category == "real_estate":
        return (
            property_profile.expected_appreciation_rate
            if property_profile is not None
            and property_profile.expected_appreciation_rate is not None
            else Decimal("0.000000")
        )
    if account.expected_annual_yield is not None:
        return account.expected_annual_yield
    if account.account_kind == AccountKind.liability:
        return Decimal("0.000000")
    return DEFAULT_CATEGORY_YIELDS.get(account.category, Decimal("0.030000"))
