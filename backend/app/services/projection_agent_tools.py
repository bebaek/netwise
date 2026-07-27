from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.projection_comparison import compare_projection_scenarios
from app.core.security import AgentPrincipal, require_agent_scopes
from app.db.models import (
    Account,
    AnnualTaxRecord,
    BalanceSnapshot,
    Household,
    IncomeSource,
    MortgageProfile,
    ProjectionScenario,
    ProjectionScenarioAccountAssumption,
    ProjectionScenarioPropertyAssumption,
    ProjectionSettings,
    ProjectionTransfer,
    RealEstateLiquidationStrategy,
    RealEstateProperty,
    RealEstateSale,
    SpendingItem,
)


def _money(value: object) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def _date_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _require_household(db: Session, principal: AgentPrincipal) -> None:
    if db.get(Household, principal.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")


def _decimal_string(value: object | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


def _timestamp_string(value: object | None) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else _date_string(value)


def _projection_scenarios(db: Session, household_id: UUID) -> list[ProjectionScenario]:
    return list(
        db.scalars(
            select(ProjectionScenario)
            .where(ProjectionScenario.household_id == household_id)
            .order_by(ProjectionScenario.is_baseline.desc(), ProjectionScenario.created_at)
        ).all()
    )


def _resolve_projection_scenario(
    db: Session,
    household_id: UUID,
    selector: str | None,
) -> ProjectionScenario:
    scenarios = _projection_scenarios(db, household_id)
    if selector is None or not selector.strip():
        baseline = next((scenario for scenario in scenarios if scenario.is_baseline), None)
        if baseline is None:
            raise ValueError("No baseline projection scenario is configured")
        return baseline

    normalized = selector.strip()
    try:
        scenario_id = UUID(normalized)
    except ValueError:
        scenario_id = None
    if scenario_id is not None:
        match = next((scenario for scenario in scenarios if scenario.id == scenario_id), None)
        if match is None:
            raise ValueError("Projection scenario was not found in the token-bound household")
        return match

    matches = [
        scenario
        for scenario in scenarios
        if scenario.name.strip().casefold() == normalized.casefold()
    ]
    if len(matches) != 1:
        raise ValueError("Scenario must identify exactly one scenario by name or ID")
    return matches[0]


def _account_names(db: Session, household_id: UUID) -> dict[UUID, str]:
    return {
        account.id: account.name
        for account in db.scalars(
            select(Account).where(Account.household_id == household_id).order_by(Account.name)
        ).all()
    }


def _latest_snapshot(db: Session, account_id: UUID) -> BalanceSnapshot | None:
    return db.scalars(
        select(BalanceSnapshot)
        .where(BalanceSnapshot.account_id == account_id)
        .order_by(BalanceSnapshot.as_of_date.desc(), BalanceSnapshot.created_at.desc())
        .limit(1)
    ).first()


def list_projection_scenarios(
    db: Session,
    principal: AgentPrincipal,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read", "projections:run")
    _require_household(db, principal)
    scenarios = _projection_scenarios(db, principal.household_id)
    return {
        "household_id": str(principal.household_id),
        "count": len(scenarios),
        "scenarios": [
            {
                "scenario_id": str(scenario.id),
                "name": scenario.name,
                "description": scenario.description,
                "is_baseline": scenario.is_baseline,
                "created_from_scenario_id": (
                    str(scenario.created_from_scenario_id)
                    if scenario.created_from_scenario_id is not None
                    else None
                ),
                "updated_at": _timestamp_string(scenario.updated_at),
            }
            for scenario in scenarios
        ],
    }


def get_property_projection_parameters(
    db: Session,
    principal: AgentPrincipal,
    property_name: str,
    scenario: str | None = None,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read", "projections:run")
    _require_household(db, principal)
    selected_scenario = _resolve_projection_scenario(db, principal.household_id, scenario)
    normalized_name = property_name.strip()
    if not normalized_name:
        raise ValueError("property_name is required")

    properties = list(
        db.scalars(
            select(RealEstateProperty)
            .where(RealEstateProperty.household_id == principal.household_id)
            .order_by(RealEstateProperty.created_at)
        ).all()
    )
    matches = [
        property_record
        for property_record in properties
        if property_record.account.name.strip().casefold() == normalized_name.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(
            "property_name must identify exactly one property in the token-bound household"
        )
    property_record = matches[0]
    account_names = _account_names(db, principal.household_id)
    latest_value = _latest_snapshot(db, property_record.account_id)
    assumption = db.scalar(
        select(ProjectionScenarioPropertyAssumption).where(
            ProjectionScenarioPropertyAssumption.scenario_id == selected_scenario.id,
            ProjectionScenarioPropertyAssumption.property_account_id == property_record.account_id,
        )
    )
    mortgage = db.scalar(
        select(MortgageProfile).where(
            MortgageProfile.household_id == principal.household_id,
            MortgageProfile.property_account_id == property_record.account_id,
        )
    )
    mortgage_balance = (
        _latest_snapshot(db, mortgage.liability_account_id) if mortgage is not None else None
    )
    sale = db.scalar(
        select(RealEstateSale).where(
            RealEstateSale.scenario_id == selected_scenario.id,
            RealEstateSale.property_account_id == property_record.account_id,
        )
    )
    liquidation = db.scalar(
        select(RealEstateLiquidationStrategy).where(
            RealEstateLiquidationStrategy.scenario_id == selected_scenario.id,
            RealEstateLiquidationStrategy.property_account_id == property_record.account_id,
        )
    )

    return {
        "scenario": {
            "scenario_id": str(selected_scenario.id),
            "name": selected_scenario.name,
            "is_baseline": selected_scenario.is_baseline,
        },
        "property": {
            "property_id": str(property_record.id),
            "account_id": str(property_record.account_id),
            "name": property_record.account.name,
            "property_type": property_record.property_type,
            "currency": property_record.account.currency,
            "latest_value": _money(latest_value.balance) if latest_value is not None else None,
            "latest_value_date": (
                latest_value.as_of_date.isoformat() if latest_value is not None else None
            ),
            "purchase_date": _date_string(property_record.purchase_date),
            "purchase_price": (
                _money(property_record.purchase_price)
                if property_record.purchase_price is not None
                else None
            ),
            "adjusted_tax_basis": (
                _money(property_record.adjusted_tax_basis)
                if property_record.adjusted_tax_basis is not None
                else None
            ),
            "down_payment": (
                _money(property_record.down_payment)
                if property_record.down_payment is not None
                else None
            ),
            "expected_appreciation_rate": _decimal_string(
                assumption.expected_appreciation_rate
                if assumption is not None
                else property_record.expected_appreciation_rate
            ),
            "property_tax_annual": (
                _money(property_record.property_tax_annual)
                if property_record.property_tax_annual is not None
                else None
            ),
            "insurance_annual": (
                _money(property_record.insurance_annual)
                if property_record.insurance_annual is not None
                else None
            ),
            "tax_and_insurance_annual": (
                _money(property_record.tax_and_insurance_annual)
                if property_record.tax_and_insurance_annual is not None
                else None
            ),
            "maintenance_rate": _decimal_string(property_record.maintenance_rate),
            "hoa_monthly": (
                _money(property_record.hoa_monthly)
                if property_record.hoa_monthly is not None
                else None
            ),
        },
        "rental": {
            "is_rental": property_record.is_rental,
            "rental_start_date": _date_string(property_record.rental_start_date),
            "monthly_market_rent": (
                _money(property_record.monthly_market_rent)
                if property_record.monthly_market_rent is not None
                else None
            ),
            "other_monthly_income": (
                _money(property_record.other_monthly_income)
                if property_record.other_monthly_income is not None
                else None
            ),
            "rent_growth_rate": _decimal_string(
                assumption.rent_growth_rate
                if assumption is not None
                else property_record.rent_growth_rate
            ),
            "vacancy_rate": _decimal_string(
                assumption.vacancy_rate if assumption is not None else property_record.vacancy_rate
            ),
            "management_fee_rate": _decimal_string(property_record.management_fee_rate),
            "utilities_annual": (
                _money(property_record.utilities_annual)
                if property_record.utilities_annual is not None
                else None
            ),
            "other_operating_expense_annual": (
                _money(property_record.other_operating_expense_annual)
                if property_record.other_operating_expense_annual is not None
                else None
            ),
            "capital_reserve_rate": _decimal_string(property_record.capital_reserve_rate),
            "deposit_account_name": account_names.get(property_record.rental_deposit_account_id),
        },
        "mortgage": (
            {
                "liability_account_id": str(mortgage.liability_account_id),
                "liability_account_name": account_names.get(mortgage.liability_account_id),
                "latest_balance": (
                    _money(mortgage_balance.balance) if mortgage_balance is not None else None
                ),
                "latest_balance_date": (
                    mortgage_balance.as_of_date.isoformat()
                    if mortgage_balance is not None
                    else None
                ),
                "original_principal": _money(mortgage.original_principal),
                "interest_rate": _decimal_string(mortgage.interest_rate),
                "term_months": mortgage.term_months,
                "start_date": mortgage.start_date.isoformat(),
                "monthly_payment": (
                    _money(mortgage.monthly_payment)
                    if mortgage.monthly_payment is not None
                    else None
                ),
                "rate_type": mortgage.rate_type,
            }
            if mortgage is not None
            else None
        ),
        "scheduled_sale": (
            {
                "sale_date": sale.sale_date.isoformat(),
                "gross_sale_price": _money(sale.gross_sale_price),
                "proceeds_account_name": account_names.get(sale.proceeds_account_id),
                "selling_expense_rate": _decimal_string(sale.selling_expense_rate),
                "estimated_tax_rate": _decimal_string(sale.estimated_tax_rate),
            }
            if sale is not None
            else None
        ),
        "automatic_liquidation": (
            {
                "enabled": liquidation.enabled,
                "optimization_mode": liquidation.optimization_mode,
                "priority": liquidation.priority,
                "earliest_sale_date": _date_string(liquidation.earliest_sale_date),
                "proceeds_account_name": account_names.get(liquidation.proceeds_account_id),
                "selling_expense_rate": _decimal_string(liquidation.selling_expense_rate),
                "estimated_tax_rate": _decimal_string(liquidation.estimated_tax_rate),
            }
            if liquidation is not None
            else None
        ),
    }


def summarize_projection_assumptions(
    db: Session,
    principal: AgentPrincipal,
    scenario: str | None = None,
    sections: list[str] | None = None,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read", "projections:run")
    _require_household(db, principal)
    selected_scenario = _resolve_projection_scenario(db, principal.household_id, scenario)
    allowed_sections = {
        "settings",
        "income",
        "spending",
        "accounts",
        "properties",
        "transfers",
        "taxes",
    }
    selected_sections = set(sections or allowed_sections)
    unknown_sections = selected_sections - allowed_sections
    if unknown_sections:
        raise ValueError(
            f"Unknown projection assumption sections: {', '.join(sorted(unknown_sections))}"
        )

    result: dict[str, object] = {
        "scenario": {
            "scenario_id": str(selected_scenario.id),
            "name": selected_scenario.name,
            "is_baseline": selected_scenario.is_baseline,
        },
        "included_sections": sorted(selected_sections),
    }
    account_names = _account_names(db, principal.household_id)

    if "settings" in selected_sections:
        settings = db.scalar(
            select(ProjectionSettings).where(ProjectionSettings.scenario_id == selected_scenario.id)
        )
        result["settings"] = (
            {
                "annual_spending": (
                    _money(settings.annual_spending)
                    if settings.annual_spending is not None
                    else None
                ),
                "spending_mode": settings.spending_mode,
                "spending_inflation_rate": _decimal_string(settings.spending_inflation_rate),
                "retirement_date": _date_string(settings.retirement_date),
                "retirement_annual_spending": (
                    _money(settings.retirement_annual_spending)
                    if settings.retirement_annual_spending is not None
                    else None
                ),
                "spending_account_name": account_names.get(settings.spending_account_id),
                "tax_account_name": account_names.get(settings.tax_account_id),
            }
            if settings is not None
            else None
        )

    if "income" in selected_sections:
        income_sources = list(
            db.scalars(
                select(IncomeSource)
                .where(IncomeSource.scenario_id == selected_scenario.id)
                .order_by(IncomeSource.start_date, IncomeSource.name)
            ).all()
        )
        result["income_sources"] = [
            {
                "name": source.name,
                "income_type": source.income_type,
                "amount": _money(source.amount),
                "currency": source.currency,
                "frequency": source.frequency,
                "start_date": source.start_date.isoformat(),
                "end_date": _date_string(source.end_date),
                "growth_rate": _decimal_string(source.growth_rate),
                "deposit_account_name": account_names.get(source.deposit_account_id),
            }
            for source in income_sources
        ]

    if "spending" in selected_sections:
        spending_items = list(
            db.scalars(
                select(SpendingItem)
                .where(SpendingItem.scenario_id == selected_scenario.id)
                .order_by(SpendingItem.category, SpendingItem.name)
            ).all()
        )
        result["spending_items"] = [
            {
                "name": item.name,
                "category": item.category,
                "annual_amount": _money(item.annual_amount),
                "retirement_annual_amount": (
                    _money(item.retirement_annual_amount)
                    if item.retirement_annual_amount is not None
                    else None
                ),
                "growth_rate": _decimal_string(item.growth_rate),
            }
            for item in spending_items
        ]

    if "accounts" in selected_sections:
        assumptions = list(
            db.scalars(
                select(ProjectionScenarioAccountAssumption)
                .where(ProjectionScenarioAccountAssumption.scenario_id == selected_scenario.id)
                .order_by(ProjectionScenarioAccountAssumption.created_at)
            ).all()
        )
        result["account_assumptions"] = [
            {
                "account_id": str(assumption.account_id),
                "account_name": account_names.get(assumption.account_id),
                "expected_annual_yield": _decimal_string(assumption.expected_annual_yield),
                "liquidation_expense_rate": _decimal_string(assumption.liquidation_expense_rate),
            }
            for assumption in assumptions
        ]

    if "properties" in selected_sections:
        properties = list(
            db.scalars(
                select(RealEstateProperty)
                .where(RealEstateProperty.household_id == principal.household_id)
                .order_by(RealEstateProperty.created_at)
            ).all()
        )
        property_assumptions = {
            assumption.property_account_id: assumption
            for assumption in db.scalars(
                select(ProjectionScenarioPropertyAssumption).where(
                    ProjectionScenarioPropertyAssumption.scenario_id == selected_scenario.id
                )
            ).all()
        }
        result["properties"] = [
            {
                "property_name": property_record.account.name,
                "property_type": property_record.property_type,
                "is_rental": property_record.is_rental,
                "expected_appreciation_rate": _decimal_string(
                    property_assumptions[property_record.account_id].expected_appreciation_rate
                    if property_record.account_id in property_assumptions
                    else property_record.expected_appreciation_rate
                ),
                "rent_growth_rate": _decimal_string(
                    property_assumptions[property_record.account_id].rent_growth_rate
                    if property_record.account_id in property_assumptions
                    else property_record.rent_growth_rate
                ),
                "vacancy_rate": _decimal_string(
                    property_assumptions[property_record.account_id].vacancy_rate
                    if property_record.account_id in property_assumptions
                    else property_record.vacancy_rate
                ),
            }
            for property_record in properties
        ]

    if "transfers" in selected_sections:
        transfers = list(
            db.scalars(
                select(ProjectionTransfer)
                .where(ProjectionTransfer.scenario_id == selected_scenario.id)
                .order_by(ProjectionTransfer.start_date, ProjectionTransfer.name)
            ).all()
        )
        result["transfers"] = [
            {
                "name": transfer.name,
                "from_account_name": account_names.get(transfer.from_account_id),
                "to_account_name": account_names.get(transfer.to_account_id),
                "annual_amount": _money(transfer.annual_amount),
                "start_date": transfer.start_date.isoformat(),
                "end_date": _date_string(transfer.end_date),
                "growth_rate": _decimal_string(transfer.growth_rate),
            }
            for transfer in transfers
        ]

    if "taxes" in selected_sections:
        tax_record = db.scalars(
            select(AnnualTaxRecord)
            .where(AnnualTaxRecord.household_id == principal.household_id)
            .order_by(AnnualTaxRecord.tax_year.desc())
            .limit(1)
        ).first()
        result["latest_tax_assumption"] = (
            {
                "tax_year": tax_record.tax_year,
                "gross_income": (
                    _money(tax_record.gross_income) if tax_record.gross_income is not None else None
                ),
                "total_taxes_paid": _money(tax_record.total_taxes_paid),
                "effective_tax_rate": _decimal_string(tax_record.effective_tax_rate),
            }
            if tax_record is not None
            else None
        )

    return result


def check_projection_readiness(
    db: Session,
    principal: AgentPrincipal,
    scenario: str | None = None,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read", "projections:run")
    _require_household(db, principal)
    selected_scenario = _resolve_projection_scenario(db, principal.household_id, scenario)
    issues: list[dict[str, object]] = []
    accounts = list(
        db.scalars(
            select(Account).where(
                Account.household_id == principal.household_id,
                Account.is_active.is_(True),
            )
        ).all()
    )
    if not accounts:
        issues.append(
            {
                "severity": "error",
                "code": "no_active_accounts",
                "message": "No active accounts are available for projection.",
            }
        )
    for account in accounts:
        if _latest_snapshot(db, account.id) is None:
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_account_balance",
                    "message": f"Account '{account.name}' has no balance snapshot.",
                    "entity_name": account.name,
                }
            )

    settings = db.scalar(
        select(ProjectionSettings).where(ProjectionSettings.scenario_id == selected_scenario.id)
    )
    if settings is None:
        issues.append(
            {
                "severity": "error",
                "code": "missing_projection_settings",
                "message": "Projection settings are not configured for this scenario.",
            }
        )
    elif settings.spending_mode == "itemized":
        spending_count = len(
            db.scalars(
                select(SpendingItem.id).where(SpendingItem.scenario_id == selected_scenario.id)
            ).all()
        )
        if spending_count == 0:
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_itemized_spending",
                    "message": "Itemized spending mode is selected but no spending items exist.",
                }
            )

    tax_record = db.scalars(
        select(AnnualTaxRecord.id)
        .where(AnnualTaxRecord.household_id == principal.household_id)
        .order_by(AnnualTaxRecord.tax_year.desc())
        .limit(1)
    ).first()
    if tax_record is None:
        issues.append(
            {
                "severity": "warning",
                "code": "missing_tax_history",
                "message": "No annual tax record is available; projected taxes may use a zero rate.",
            }
        )

    property_assumptions = {
        assumption.property_account_id: assumption
        for assumption in db.scalars(
            select(ProjectionScenarioPropertyAssumption).where(
                ProjectionScenarioPropertyAssumption.scenario_id == selected_scenario.id
            )
        ).all()
    }
    properties = list(
        db.scalars(
            select(RealEstateProperty).where(
                RealEstateProperty.household_id == principal.household_id
            )
        ).all()
    )
    for property_record in properties:
        property_name = property_record.account.name
        if _latest_snapshot(db, property_record.account_id) is None:
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_property_value",
                    "message": f"Property '{property_name}' has no current value snapshot.",
                    "entity_name": property_name,
                }
            )
        assumption = property_assumptions.get(property_record.account_id)
        appreciation = (
            assumption.expected_appreciation_rate
            if assumption is not None
            else property_record.expected_appreciation_rate
        )
        if appreciation is None:
            issues.append(
                {
                    "severity": "warning",
                    "code": "missing_property_appreciation",
                    "message": f"Property '{property_name}' has no appreciation assumption.",
                    "entity_name": property_name,
                }
            )
        if property_record.is_rental and property_record.monthly_market_rent is None:
            issues.append(
                {
                    "severity": "warning",
                    "code": "missing_market_rent",
                    "message": f"Rental property '{property_name}' has no monthly market rent.",
                    "entity_name": property_name,
                }
            )

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "scenario": {
            "scenario_id": str(selected_scenario.id),
            "name": selected_scenario.name,
            "is_baseline": selected_scenario.is_baseline,
        },
        "ready": error_count == 0,
        "issue_counts": {"errors": error_count, "warnings": warning_count},
        "issues": issues,
    }


def summarize_projection_comparison(
    db: Session,
    principal: AgentPrincipal,
    scenario_ids: list[str] | None,
    start_year: int,
    end_year: int,
    scenarios: list[str] | None = None,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read", "projections:run")
    _require_household(db, principal)
    if scenario_ids is not None and scenarios is not None:
        raise ValueError("Provide either scenarios or scenario_ids, not both")
    selectors = scenarios if scenarios is not None else scenario_ids
    if selectors is None or not 2 <= len(selectors) <= 4:
        raise ValueError("Choose between two and four projection scenarios")
    resolved_scenarios = [
        _resolve_projection_scenario(db, principal.household_id, selector) for selector in selectors
    ]
    parsed_scenario_ids = [scenario.id for scenario in resolved_scenarios]
    if len(set(parsed_scenario_ids)) != len(parsed_scenario_ids):
        raise ValueError("Projection scenarios must be unique")
    if start_year > end_year:
        raise ValueError("start_year must not be after end_year")

    comparison = compare_projection_scenarios(
        db,
        principal.household_id,
        scenario_ids=parsed_scenario_ids,
        start_year=start_year,
        end_year=end_year,
        interval="annual",
    )
    return {
        "household_id": str(principal.household_id),
        "start_year": comparison["start_year"],
        "end_year": comparison["end_year"],
        "scenarios": [
            {
                "scenario_id": str(scenario["scenario_id"]),
                "scenario_name": scenario["scenario_name"],
                "ending_net_worth": _money(scenario["ending_net_worth"]),
                "lowest_net_worth": _money(scenario["lowest_net_worth"]),
                "lowest_liquid_assets_total": _money(scenario["lowest_liquid_assets_total"]),
                "cumulative_projected_income": _money(scenario["cumulative_projected_income"]),
                "cumulative_projected_taxes": _money(scenario["cumulative_projected_taxes"]),
                "cumulative_projected_spending": _money(scenario["cumulative_projected_spending"]),
                "retirement_date": _date_string(scenario["retirement_date"]),
                "first_unfunded_date": _date_string(scenario["first_unfunded_date"]),
                "warnings": list(scenario["warnings"]),
            }
            for scenario in comparison["scenarios"]
        ],
    }
