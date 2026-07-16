from datetime import date
from decimal import Decimal

from app.db.models import MortgageProfile


MONTHS_PER_YEAR = Decimal("12")


def estimate_mortgage_balance(profile: MortgageProfile, as_of_date: date) -> Decimal:
    """Estimate remaining mortgage balance from amortization profile.

    This is a deterministic planning estimate. It assumes a standard amortizing loan
    with fixed monthly payments and clamps the result between zero and original
    principal.
    """
    principal = profile.original_principal
    elapsed_months = months_between(profile.start_date, as_of_date)
    if elapsed_months <= 0:
        return principal
    if elapsed_months >= profile.term_months:
        return Decimal("0.00")

    monthly_rate = profile.interest_rate / MONTHS_PER_YEAR
    if monthly_rate == 0:
        balance = principal * Decimal(profile.term_months - elapsed_months) / Decimal(
            profile.term_months
        )
    else:
        one_plus_rate = Decimal("1") + monthly_rate
        total_factor = one_plus_rate**profile.term_months
        elapsed_factor = one_plus_rate**elapsed_months
        balance = principal * (total_factor - elapsed_factor) / (total_factor - Decimal("1"))

    return balance.quantize(Decimal("0.01")).max(Decimal("0.00")).min(principal)


def months_between(start_date: date, end_date: date) -> int:
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return months
