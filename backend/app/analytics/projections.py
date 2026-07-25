from calendar import monthrange
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.mortgage import estimate_mortgage_balance
from app.analytics.projection_contracts import (
    ProjectionAccount,
    ProjectionEvent,
    ProjectionLiquidationStrategy,
    ProjectionMortgage,
    ProjectionProperty,
    ProjectionPropertySale,
    ProjectionTransferInput,
)
from app.analytics.projection_input import ProjectionInput, load_projection_input
from app.analytics.projection_property_sales import (
    AutomaticPropertySaleContext,
    ProjectedPropertySale,
    apply_property_sale,
    ordered_march_sale_schedules,
)
from app.analytics.projection_returns import (
    annual_return_for_account,
    project_balance_with_return,
)
from app.analytics.projection_results import (
    ProjectionAccountResult,
    ProjectionCashFlowResult,
    ProjectionPointResult,
    ProjectionResult,
    ProjectionSpendingItemResult,
    PropertySaleOptimizationResult,
    PropertySaleOptimizationSelectionResult,
    format_projection_result,
)
from app.analytics.projection_income import project_income_source_for_period
from app.analytics.projection_tax import (
    effective_income_tax,
    property_sale_tax_basis_warnings,
    taxable_income_for_period,
    withdrawal_taxes,
)
from app.analytics.projection_spending import (
    active_months_in_period,
    amortized_monthly_payment,
    project_owner_mortgage_spending_for_period,
    project_owner_property_spending_for_period,
    project_spending_for_period,
    project_spending_items_for_period,
)
from app.analytics.projection_withdrawals import (
    LIQUIDITY_CLASSES,
    WithdrawalResult,
    withdraw_from_account_pool,
)
from app.db.models import AccountEventType, AccountKind

DEFAULT_SPENDING_INFLATION_RATE = Decimal("0.030000")
TAXABLE_INVESTMENT_CATEGORIES = {"taxable_investment", "brokerage"}


def _current_date() -> date:
    return date.today()


CASH_FLOW_CATEGORY_PRIORITY = {
    "cash": 0,
    "checking": 0,
    "savings": 1,
    "taxable_investment": 2,
    "brokerage": 2,
    "retirement": 3,
}


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
) -> dict:
    """Run the deterministic projection and format its API response."""
    result = _calculate_projection_result_from_input(
        projection_input,
        start_year=start_year,
        end_year=end_year,
        annual_spending=annual_spending,
        spending_inflation_rate=spending_inflation_rate,
        spending_account_id=spending_account_id,
        tax_account_id=tax_account_id,
        interval=interval,
    )
    return format_projection_result(result)


def _calculate_projection_result_from_input(
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
) -> ProjectionResult:
    """Run the deterministic simulation without database or API concerns."""
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

    points: list[ProjectionPointResult] = []
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

            annual_return = annual_return_for_account(account, property_profiles.get(account.id))
            balances[account.id] = project_balance_with_return(
                balances[account.id], annual_return, months_per_period
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
            income_amount = project_income_source_for_period(
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
        taxable_income = taxable_income_for_period(
            projected_income,
            projected_rental_income,
            projected_rental_expenses,
        )
        income_taxes = effective_income_tax(taxable_income, tax_rate)
        if use_itemized_spending:
            projected_spending_breakdown = project_spending_items_for_period(
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
            projected_non_mortgage_spending = project_spending_for_period(
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
        projected_owner_property_spending_breakdown = project_owner_property_spending_for_period(
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
        projected_mortgage_spending = project_owner_mortgage_spending_for_period(
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
        projected_taxes = (income_taxes + withdrawal_taxes(withdrawal_result, tax_rate)).quantize(
            Decimal("0.01")
        )
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
                projected_taxes + withdrawal_taxes(tax_payment_result, tax_rate)
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

        account_points = tuple(
            ProjectionAccountResult(
                account_id=account.id,
                name=account.name,
                account_kind=account.account_kind,
                category=account.category,
                liquidity_class=account.liquidity_class,
                projected_balance=balances[account.id],
            )
            for account in accounts
        )
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
            ProjectionPointResult(
                year=year,
                as_of_date=as_of_date,
                net_worth=assets_total - liabilities_total,
                assets_total=assets_total,
                liabilities_total=liabilities_total,
                projected_income=projected_income,
                projected_rental_income=projected_rental_income,
                projected_rental_expenses=projected_rental_expenses,
                projected_taxes=projected_taxes,
                projected_spending=projected_spending,
                projected_owner_property_spending=projected_owner_property_spending,
                projected_mortgage_spending=projected_mortgage_spending,
                projected_spending_breakdown=tuple(
                    ProjectionSpendingItemResult(**item) for item in projected_spending_breakdown
                ),
                projected_liquidation_expenses=projected_liquidation_expenses,
                projected_unfunded_cash_flow=projected_unfunded_cash_flow,
                net_cash_flow=net_cash_flow,
                retirement_phase=(
                    effective_retirement_date is not None
                    and effective_retirement_date <= as_of_date
                ),
                cash_flows=tuple(ProjectionCashFlowResult(**flow) for flow in cash_flows),
                accounts=account_points,
            )
        )

    warnings = property_sale_tax_basis_warnings(
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
    result = ProjectionResult(
        household_id=household_id,
        start_year=start_year,
        end_year=end_year,
        interval=interval,
        spending_mode="itemized" if use_itemized_spending else "manual",
        retirement_date=effective_retirement_date,
        first_retirement_withdrawal_date=_first_retirement_withdrawal_date(points, accounts),
        first_unfunded_date=next(
            (
                point.as_of_date
                for point in points
                if point.projected_unfunded_cash_flow > Decimal("0.00")
            ),
            None,
        ),
        warnings=tuple(warnings),
        points=tuple(points),
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
    strategies: Sequence[ProjectionLiquidationStrategy],
) -> ProjectionResult:
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
    best_result: ProjectionResult | None = None
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
        result = _calculate_projection_result_from_input(
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
        best_result.points, projection_input.accounts
    )
    candidate_end_year = first_retirement_date.year if first_retirement_date else end_year
    while True:
        for schedule in ordered_march_sale_schedules(
            ordered_strategies,
            start_year=start_year,
            end_year=candidate_end_year,
            not_before=max(date(start_year, 1, 1), _current_date()),
        ):
            evaluate(schedule)

        if best_result is None:
            raise ValueError("Unable to evaluate property sale schedules")
        expanded_retirement_date = _first_retirement_withdrawal_date(
            best_result.points, projection_input.accounts
        )
        expanded_end_year = expanded_retirement_date.year if expanded_retirement_date else end_year
        if expanded_end_year <= candidate_end_year or candidate_end_year == end_year:
            break
        candidate_end_year = min(expanded_end_year, end_year)

    accounts_by_id = {account.id: account for account in projection_input.accounts}
    first_retirement_date = _first_retirement_withdrawal_date(
        best_result.points, projection_input.accounts
    )
    return replace(
        best_result,
        property_sale_optimization=PropertySaleOptimizationResult(
            mode="maximize_liquid_runway",
            candidate_month=3,
            candidate_day=1,
            schedules_evaluated=schedules_evaluated,
            first_retirement_withdrawal_date=first_retirement_date,
            selected_sales=tuple(
                PropertySaleOptimizationSelectionResult(
                    property_account_id=strategy.property_account_id,
                    property_name=accounts_by_id[strategy.property_account_id].name,
                    sale_date=best_schedule[strategy.property_account_id],
                )
                for strategy in ordered_strategies
            ),
        ),
    )


def _liquid_runway_score(
    result: ProjectionResult,
    accounts: Sequence[ProjectionAccount],
) -> tuple[int, int, Decimal, Decimal]:
    points = result.points
    retirement_ids = {account.id for account in accounts if account.category == "retirement"}
    retirement_index = len(points) + 1
    for index, point in enumerate(points):
        if any(
            cash_flow.account_id in retirement_ids and cash_flow.amount < Decimal("0.00")
            for cash_flow in point.cash_flows
        ):
            retirement_index = index
            break

    unfunded_index = len(points) + 1
    for index, point in enumerate(points):
        if point.projected_unfunded_cash_flow > Decimal("0.00"):
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
            account_point.projected_balance
            for account_point in points[balance_point_index].accounts
            if account_point.account_id in liquid_account_ids
        ),
        Decimal("0.00"),
    )
    return (
        retirement_index,
        unfunded_index,
        liquid_balance,
        points[-1].net_worth,
    )


def _first_retirement_withdrawal_date(
    points: Sequence[ProjectionPointResult],
    accounts: Sequence[ProjectionAccount],
) -> date | None:
    retirement_ids = {account.id for account in accounts if account.category == "retirement"}
    for point in points:
        if any(
            cash_flow.account_id in retirement_ids and cash_flow.amount < Decimal("0.00")
            for cash_flow in point.cash_flows
        ):
            return point.as_of_date
    return None


def _projected_transfer_for_period(
    transfer: ProjectionTransferInput,
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


def _validate_cash_flow_account(
    accounts_by_id: dict[UUID, ProjectionAccount], account_id: UUID | None, label: str
) -> None:
    if account_id is None:
        return
    account = accounts_by_id.get(account_id)
    if account is None or account.account_kind != AccountKind.asset:
        raise ValueError(f"{label} must be an active asset account in the household")


def _cash_flow_target_account(
    accounts: Sequence[ProjectionAccount],
    accounts_by_id: dict[UUID, ProjectionAccount],
    account_id: UUID | None,
) -> ProjectionAccount | None:
    if account_id is not None:
        return accounts_by_id[account_id]
    asset_accounts = [account for account in accounts if account.account_kind == AccountKind.asset]
    if not asset_accounts:
        return None
    return min(asset_accounts, key=_cash_flow_priority)


def _apply_rental_cash_flow(
    property_profile: ProjectionProperty,
    accounts: Sequence[ProjectionAccount],
    accounts_by_id: dict[UUID, ProjectionAccount],
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
    active_months = active_months_in_period(
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
    property_profile: ProjectionProperty,
    mortgage_profile: ProjectionMortgage | None,
    accounts: Sequence[ProjectionAccount],
    accounts_by_id: dict[UUID, ProjectionAccount],
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
    active_months = active_months_in_period(
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

    monthly_payment = mortgage_profile.monthly_payment or amortized_monthly_payment(
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


def _apply_account_cash_flow(
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    account: ProjectionAccount,
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


def _apply_real_estate_sale(
    accounts: Sequence[ProjectionAccount],
    accounts_by_id: dict[UUID, ProjectionAccount],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    sale: ProjectionPropertySale | ProjectedPropertySale,
    property_profile: ProjectionProperty | None,
    mortgage_profile: ProjectionMortgage | None,
    sold_mortgage_account_ids: set[UUID],
    tax_rate: Decimal,
    basis_balances: dict[UUID, Decimal] | None = None,
) -> WithdrawalResult:
    return apply_property_sale(
        accounts_by_id,
        balances,
        cash_flows,
        sale,
        property_profile,
        mortgage_profile,
        sold_mortgage_account_ids,
        basis_balances,
        lambda shortfall: _withdraw_from_assets(
            [account for account in accounts if account.id != sale.property_account_id],
            accounts_by_id,
            balances,
            cash_flows,
            shortfall,
            "property_sale_shortfall",
            None,
            tax_rate,
            None,
            basis_balances,
        ),
    )


def _apply_projection_event(
    accounts_by_id: dict[UUID, ProjectionAccount],
    balances: dict[UUID, Decimal],
    cash_flows: list[dict],
    event: ProjectionEvent,
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


def _projection_event_amount(event: ProjectionEvent) -> Decimal:
    if event.event_type in AccountEventOutflowTypes:
        return -abs(event.amount)
    if event.event_type in AccountEventInflowTypes:
        return abs(event.amount)
    return event.amount


def _withdraw_from_assets(
    accounts: Sequence[ProjectionAccount],
    accounts_by_id: dict[UUID, ProjectionAccount],
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
        return withdraw_from_account_pool(
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
    funding_attempt = withdraw_from_account_pool(
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

        funding_attempt = withdraw_from_account_pool(
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
        funding_attempt = withdraw_from_account_pool(
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


def _cash_flow_priority(account: ProjectionAccount) -> tuple[int, str]:
    return (CASH_FLOW_CATEGORY_PRIORITY.get(account.category, 99), account.name)
