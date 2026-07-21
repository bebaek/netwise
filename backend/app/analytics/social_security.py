from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

# This deliberately uses one published-law baseline and exposes its version in every result.
# It is a planning estimate, not an SSA benefit determination.
LAW_ASSUMPTION_YEAR = 2025
CALCULATION_VERSION = "ssa-ballpark-2025.1"
FIRST_BEND_POINT = Decimal("1226")
SECOND_BEND_POINT = Decimal("7391")
TAXABLE_MAXIMUM = Decimal("176100")


@dataclass(frozen=True)
class SocialSecurityCalculation:
    monthly_benefit: Decimal
    lower_monthly_benefit: Decimal
    upper_monthly_benefit: Decimal
    benefit_at_full_retirement_age: Decimal
    full_retirement_age_months: int
    calculation_version: str = CALCULATION_VERSION
    law_assumption_year: int = LAW_ASSUMPTION_YEAR


def full_retirement_age_months(birth_year: int) -> int:
    if birth_year <= 1937:
        return 65 * 12
    if birth_year <= 1942:
        return 65 * 12 + (birth_year - 1937) * 2
    if birth_year <= 1954:
        return 66 * 12
    if birth_year <= 1959:
        return 66 * 12 + (birth_year - 1954) * 2
    return 67 * 12


def age_in_months(date_of_birth: date, as_of_date: date) -> int:
    months = (as_of_date.year - date_of_birth.year) * 12 + as_of_date.month - date_of_birth.month
    if as_of_date.day < date_of_birth.day:
        months -= 1
    return months


def claiming_adjustment(claim_age_months: int, fra_months: int) -> Decimal:
    difference = claim_age_months - fra_months
    if difference < 0:
        early_months = abs(difference)
        first_36 = min(early_months, 36)
        additional = max(early_months - 36, 0)
        reduction = Decimal(first_36) * Decimal(5) / Decimal(900)
        reduction += Decimal(additional) * Decimal(5) / Decimal(1200)
        return max(Decimal("0"), Decimal("1") - reduction)
    delayed_months = min(difference, max(70 * 12 - fra_months, 0))
    return Decimal("1") + Decimal(delayed_months) * Decimal(2) / Decimal(300)


def _primary_insurance_amount(aime: Decimal) -> Decimal:
    first = min(aime, FIRST_BEND_POINT) * Decimal("0.90")
    second = min(max(aime - FIRST_BEND_POINT, Decimal("0")), SECOND_BEND_POINT - FIRST_BEND_POINT)
    third = max(aime - SECOND_BEND_POINT, Decimal("0"))
    return first + second * Decimal("0.32") + third * Decimal("0.15")


def calculate_ballpark_benefit(
    *,
    date_of_birth: date,
    claiming_date: date,
    current_covered_earnings: Decimal,
    completed_work_years: int,
    expected_work_end_date: date | None,
    earnings_pattern: str,
    cola_rate: Decimal,
) -> SocialSecurityCalculation:
    claim_age = age_in_months(date_of_birth, claiming_date)
    if claim_age < 62 * 12:
        raise ValueError("Claiming date must be at or after age 62")
    if completed_work_years < 0 or completed_work_years > 50:
        raise ValueError("Completed work years must be between 0 and 50")
    if current_covered_earnings < 0:
        raise ValueError("Current covered earnings cannot be negative")

    pattern_factor = {
        "lower": Decimal("0.70"),
        "steady": Decimal("1.00"),
        "rising": Decimal("0.85"),
    }.get(earnings_pattern)
    if pattern_factor is None:
        raise ValueError("Unknown earnings pattern")

    work_end_date = min(expected_work_end_date or claiming_date, claiming_date)
    future_work_years = max(work_end_date.year - LAW_ASSUMPTION_YEAR, 0)
    credited_years = min(completed_work_years + future_work_years, 35)
    if credited_years < 10:
        raise ValueError("Estimated work history must include at least 10 years")
    representative_earnings = min(current_covered_earnings, TAXABLE_MAXIMUM) * pattern_factor
    aime = representative_earnings * Decimal(credited_years) / Decimal(35 * 12)
    fra_benefit_today = _primary_insurance_amount(aime)
    fra_months = full_retirement_age_months(date_of_birth.year)
    claim_benefit_today = fra_benefit_today * claiming_adjustment(claim_age, fra_months)

    # Convert the current-dollar estimate to a claim-date cash flow so it composes with
    # Netwise's nominal spending projection. COLA after claiming is handled by IncomeSource.
    years_to_claim = max(claiming_date.year - LAW_ASSUMPTION_YEAR, 0)
    claim_date_benefit = claim_benefit_today * ((Decimal("1") + cola_rate) ** years_to_claim)
    monthly = claim_date_benefit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    uncertainty = Decimal("0.15") if credited_years >= 25 else Decimal("0.25")

    return SocialSecurityCalculation(
        monthly_benefit=monthly,
        lower_monthly_benefit=(monthly * (Decimal("1") - uncertainty)).quantize(Decimal("0.01")),
        upper_monthly_benefit=(monthly * (Decimal("1") + uncertainty)).quantize(Decimal("0.01")),
        benefit_at_full_retirement_age=fra_benefit_today.quantize(Decimal("0.01")),
        full_retirement_age_months=fra_months,
    )


def calculate_manual_benefit(
    *, date_of_birth: date, monthly_benefit: Decimal
) -> SocialSecurityCalculation:
    if monthly_benefit <= 0:
        raise ValueError("Manual monthly benefit must be greater than zero")
    amount = monthly_benefit.quantize(Decimal("0.01"))
    return SocialSecurityCalculation(
        monthly_benefit=amount,
        lower_monthly_benefit=amount,
        upper_monthly_benefit=amount,
        benefit_at_full_retirement_age=amount,
        full_retirement_age_months=full_retirement_age_months(date_of_birth.year),
        calculation_version="manual-entry-1",
    )
