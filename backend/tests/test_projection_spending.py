from datetime import date
from decimal import Decimal
from uuid import UUID

from app.analytics.projection_contracts import (
    ProjectionAccount,
    ProjectionMortgage,
    ProjectionProperty,
    ProjectionSpendingItem,
)
from app.analytics.projection_spending import (
    project_owner_mortgage_spending_for_period,
    project_owner_property_spending_for_period,
    project_spending_for_period,
    project_spending_items_for_period,
    scheduled_mortgage_payment_months,
)


def test_spending_blends_working_and_retirement_amounts_within_period() -> None:
    amount = project_spending_for_period(
        (2026, Decimal("12000.00")),
        (2026, Decimal("6000.00")),
        date(2026, 7, 1),
        date(2026, 1, 1),
        date(2026, 12, 31),
        12,
        Decimal("0.00"),
    )

    assert amount == Decimal("8975.34")


def test_itemized_spending_uses_item_growth_and_retirement_fallbacks() -> None:
    items = [
        ProjectionSpendingItem(
            name="Food",
            category="food",
            annual_amount=Decimal("12000.00"),
            retirement_annual_amount=Decimal("6000.00"),
            growth_rate=Decimal("0.00"),
        ),
        ProjectionSpendingItem(
            name="Travel",
            category="travel",
            annual_amount=Decimal("2400.00"),
            retirement_annual_amount=None,
            growth_rate=None,
        ),
    ]

    breakdown = project_spending_items_for_period(
        items,
        date(2026, 7, 1),
        2026,
        date(2026, 1, 1),
        date(2026, 12, 31),
        12,
        Decimal("0.00"),
    )

    assert breakdown == [
        {"name": "Food", "category": "food", "amount": Decimal("8975.34")},
        {"name": "Travel", "category": "travel", "amount": Decimal("2400.00")},
    ]


def test_owner_property_spending_prorates_active_months_and_stops_after_sale() -> None:
    account_id = UUID(int=1)
    account = ProjectionAccount(
        id=account_id,
        name="Home",
        account_kind="asset",
        category="real_estate",
        liquidity_class="illiquid",
        retirement_tax_treatment=None,
        expected_annual_yield=None,
        liquidation_expense_rate=None,
    )
    profile = _property(
        account_id,
        purchase_date=date(2026, 7, 15),
        property_tax_annual=Decimal("4000.00"),
        insurance_annual=Decimal("2000.00"),
        tax_and_insurance_annual=Decimal("12000.00"),
    )

    breakdown = project_owner_property_spending_for_period(
        [profile],
        {account_id: account},
        {account_id: Decimal("500000.00")},
        2026,
        date(2026, 1, 1),
        date(2026, 12, 31),
        12,
        Decimal("0.00"),
    )

    assert breakdown == [
        {
            "name": "Home property tax and insurance",
            "category": "housing",
            "amount": Decimal("6000.00"),
        }
    ]
    assert (
        project_owner_property_spending_for_period(
            [profile],
            {account_id: account},
            {account_id: Decimal("0.00")},
            2026,
            date(2026, 1, 1),
            date(2026, 12, 31),
            12,
            Decimal("0.00"),
        )
        == []
    )


def test_owner_mortgage_spending_uses_schedule_and_stops_after_sale() -> None:
    liability_account_id = UUID(int=2)
    profile = ProjectionMortgage(
        liability_account_id=liability_account_id,
        property_account_id=UUID(int=1),
        original_principal=Decimal("12000.00"),
        interest_rate=Decimal("0.00"),
        term_months=12,
        start_date=date(2026, 1, 1),
        monthly_payment=None,
    )

    assert scheduled_mortgage_payment_months(profile, date(2026, 1, 1), date(2026, 12, 31)) == 11
    assert project_owner_mortgage_spending_for_period(
        [profile], date(2026, 1, 1), date(2026, 12, 31), set()
    ) == Decimal("11000.00")
    assert project_owner_mortgage_spending_for_period(
        [profile],
        date(2026, 1, 1),
        date(2026, 12, 31),
        {liability_account_id},
    ) == Decimal("0.00")


def _property(
    account_id: UUID,
    *,
    purchase_date: date | None,
    property_tax_annual: Decimal | None,
    insurance_annual: Decimal | None,
    tax_and_insurance_annual: Decimal | None,
) -> ProjectionProperty:
    return ProjectionProperty(
        account_id=account_id,
        purchase_date=purchase_date,
        purchase_price=None,
        adjusted_tax_basis=None,
        expected_appreciation_rate=None,
        property_tax_annual=property_tax_annual,
        insurance_annual=insurance_annual,
        tax_and_insurance_annual=tax_and_insurance_annual,
        maintenance_rate=None,
        hoa_monthly=None,
        is_rental=False,
        rental_start_date=None,
        monthly_market_rent=None,
        other_monthly_income=None,
        rent_growth_rate=None,
        vacancy_rate=None,
        management_fee_rate=None,
        utilities_annual=None,
        other_operating_expense_annual=None,
        capital_reserve_rate=None,
        rental_deposit_account_id=None,
    )
