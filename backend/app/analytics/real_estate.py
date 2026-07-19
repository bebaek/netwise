from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.mortgage import estimate_mortgage_balance
from app.db.models import BalanceSnapshot, MortgageProfile, RealEstateProperty

MONEY = Decimal("0.01")
RATE = Decimal("0.000001")
MONTHS_PER_YEAR = Decimal("12")
DAYS_PER_YEAR = Decimal("365.2425")


def calculate_real_estate_analytics(db: Session, household_id: UUID) -> list[dict]:
    """Calculate valuation-based property performance and estimated rental returns.

    Appreciation uses recorded property valuations. Rental returns use the property's
    current planning assumptions and are intentionally marked as estimates.
    """

    properties = db.scalars(
        select(RealEstateProperty)
        .where(RealEstateProperty.household_id == household_id)
        .order_by(RealEstateProperty.created_at)
    ).all()
    mortgages = {
        mortgage.property_account_id: mortgage
        for mortgage in db.scalars(
            select(MortgageProfile).where(MortgageProfile.household_id == household_id)
        ).all()
        if mortgage.property_account_id is not None
    }

    return [_property_analytics(db, property_record, mortgages.get(property_record.account_id)) for property_record in properties]


def _property_analytics(
    db: Session,
    property_record: RealEstateProperty,
    mortgage: MortgageProfile | None,
) -> dict:
    snapshots = list(
        db.scalars(
            select(BalanceSnapshot)
            .where(BalanceSnapshot.account_id == property_record.account_id)
            .order_by(BalanceSnapshot.as_of_date, BalanceSnapshot.created_at)
        ).all()
    )
    latest = snapshots[-1] if snapshots else None
    current_value = latest.balance if latest is not None else None
    valuation_date = latest.as_of_date if latest is not None else None

    appreciation_amount = None
    appreciation_rate = None
    annualized_appreciation_rate = None
    if current_value is not None and property_record.purchase_price is not None:
        appreciation_amount = (current_value - property_record.purchase_price).quantize(MONEY)
        if property_record.purchase_price > 0:
            appreciation_rate = (appreciation_amount / property_record.purchase_price).quantize(RATE)
            if (
                property_record.purchase_date is not None
                and valuation_date is not None
                and valuation_date > property_record.purchase_date
                and current_value > 0
            ):
                years = Decimal((valuation_date - property_record.purchase_date).days) / DAYS_PER_YEAR
                annualized = float(current_value / property_record.purchase_price) ** (1 / float(years)) - 1
                annualized_appreciation_rate = Decimal(str(annualized)).quantize(RATE)

    mortgage_balance = None
    mortgage_balance_estimated = False
    if mortgage is not None and valuation_date is not None:
        mortgage_snapshot = db.scalars(
            select(BalanceSnapshot)
            .where(
                BalanceSnapshot.account_id == mortgage.liability_account_id,
                BalanceSnapshot.as_of_date <= valuation_date,
            )
            .order_by(BalanceSnapshot.as_of_date.desc(), BalanceSnapshot.created_at.desc())
            .limit(1)
        ).first()
        if mortgage_snapshot is not None:
            mortgage_balance = mortgage_snapshot.balance
        else:
            mortgage_balance = estimate_mortgage_balance(mortgage, valuation_date)
            mortgage_balance_estimated = True

    equity = None
    if current_value is not None:
        equity = (current_value - (mortgage_balance or Decimal("0.00"))).quantize(MONEY)

    rental = _estimated_rental_returns(property_record, current_value, mortgage)
    limitations = []
    if latest is None:
        limitations.append("Add a property valuation snapshot to calculate performance.")
    if property_record.purchase_price is None:
        limitations.append("Add the purchase price to calculate appreciation.")
    if property_record.purchase_date is None:
        limitations.append("Add the purchase date to calculate annualized appreciation.")
    if mortgage_balance_estimated:
        limitations.append("Mortgage balance is estimated because no linked balance snapshot exists on or before the valuation date.")
    if property_record.is_rental:
        limitations.append("Rental returns use current planning assumptions, not recorded historical income and expenses.")

    return {
        "property_id": property_record.id,
        "account_id": property_record.account_id,
        "property_name": property_record.account.name,
        "valuation_date": valuation_date,
        "current_value": current_value,
        "purchase_date": property_record.purchase_date,
        "purchase_price": property_record.purchase_price,
        "expected_appreciation_rate": property_record.expected_appreciation_rate,
        "appreciation_amount": appreciation_amount,
        "appreciation_rate": appreciation_rate,
        "annualized_appreciation_rate": annualized_appreciation_rate,
        "mortgage_balance": mortgage_balance,
        "mortgage_balance_estimated": mortgage_balance_estimated,
        "equity": equity,
        **rental,
        "valuation_history": [
            {"as_of_date": snapshot.as_of_date, "value": snapshot.balance}
            for snapshot in snapshots
        ],
        "limitations": limitations,
    }


def _estimated_rental_returns(
    property_record: RealEstateProperty,
    current_value: Decimal | None,
    mortgage: MortgageProfile | None,
) -> dict:
    empty = {
        "estimated_annual_rental_income": None,
        "estimated_noi": None,
        "estimated_annual_cash_flow": None,
        "gross_rental_yield": None,
        "cap_rate": None,
        "cash_on_cash_return": None,
    }
    if not property_record.is_rental or current_value is None or current_value <= 0:
        return empty

    gross_income = (
        (property_record.monthly_market_rent or Decimal("0.00"))
        + (property_record.other_monthly_income or Decimal("0.00"))
    ) * MONTHS_PER_YEAR
    effective_income = gross_income * (Decimal("1") - (property_record.vacancy_rate or Decimal("0")))
    management = effective_income * (property_record.management_fee_rate or Decimal("0"))
    tax_and_insurance = property_record.tax_and_insurance_annual
    if tax_and_insurance is None:
        tax_and_insurance = (property_record.property_tax_annual or Decimal("0.00")) + (
            property_record.insurance_annual or Decimal("0.00")
        )
    operating_expenses = (
        management
        + tax_and_insurance
        + current_value * (property_record.maintenance_rate or Decimal("0"))
        + (property_record.hoa_monthly or Decimal("0.00")) * MONTHS_PER_YEAR
        + (property_record.utilities_annual or Decimal("0.00"))
        + (property_record.other_operating_expense_annual or Decimal("0.00"))
        + current_value * (property_record.capital_reserve_rate or Decimal("0"))
    )
    noi = effective_income - operating_expenses
    debt_service = _annual_debt_service(mortgage)
    cash_flow = noi - debt_service

    return {
        "estimated_annual_rental_income": gross_income.quantize(MONEY),
        "estimated_noi": noi.quantize(MONEY),
        "estimated_annual_cash_flow": cash_flow.quantize(MONEY),
        "gross_rental_yield": (gross_income / current_value).quantize(RATE),
        "cap_rate": (noi / current_value).quantize(RATE),
        "cash_on_cash_return": (
            (cash_flow / property_record.down_payment).quantize(RATE)
            if property_record.down_payment is not None and property_record.down_payment > 0
            else None
        ),
    }


def _annual_debt_service(mortgage: MortgageProfile | None) -> Decimal:
    if mortgage is None:
        return Decimal("0.00")
    if mortgage.monthly_payment is not None:
        return mortgage.monthly_payment * MONTHS_PER_YEAR
    monthly_rate = mortgage.interest_rate / MONTHS_PER_YEAR
    if monthly_rate == 0:
        monthly_payment = mortgage.original_principal / Decimal(mortgage.term_months)
    else:
        factor = (Decimal("1") + monthly_rate) ** mortgage.term_months
        monthly_payment = mortgage.original_principal * monthly_rate * factor / (factor - Decimal("1"))
    return (monthly_payment * MONTHS_PER_YEAR).quantize(MONEY, rounding=ROUND_HALF_UP)
