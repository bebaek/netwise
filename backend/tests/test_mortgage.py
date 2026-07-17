from datetime import date
from decimal import Decimal

from app.analytics.mortgage import estimate_mortgage_balance, months_between
from app.db.models import MortgageProfile


def test_months_between():
    assert months_between(date(2020, 1, 15), date(2020, 1, 15)) == 0
    assert months_between(date(2020, 1, 15), date(2020, 2, 14)) == 0
    assert months_between(date(2020, 1, 15), date(2020, 2, 15)) == 1
    assert months_between(date(2020, 1, 15), date(2021, 1, 15)) == 12


def test_estimate_zero_interest_mortgage_balance():
    profile = MortgageProfile(
        original_principal=Decimal("300000.00"),
        interest_rate=Decimal("0.000000"),
        term_months=300,
        start_date=date(2020, 1, 1),
    )

    assert estimate_mortgage_balance(profile, date(2019, 12, 31)) == Decimal("0.00")
    assert estimate_mortgage_balance(profile, date(2020, 1, 1)) == Decimal("300000.00")
    assert estimate_mortgage_balance(profile, date(2020, 2, 1)) == Decimal("299000.00")
    assert estimate_mortgage_balance(profile, date(2045, 1, 1)) == Decimal("0.00")
