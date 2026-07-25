from decimal import Decimal

from app.analytics.projection_contracts import ProjectionAccount, ProjectionProperty

DEFAULT_CATEGORY_RETURNS = {
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
DEFAULT_FALLBACK_RETURN = Decimal("0.030000")


def annual_return_for_account(
    account: ProjectionAccount,
    property_profile: ProjectionProperty | None,
) -> Decimal:
    """Resolve the deterministic annual return assumption for an account."""
    if account.category == "real_estate":
        return (
            property_profile.expected_appreciation_rate
            if property_profile is not None
            and property_profile.expected_appreciation_rate is not None
            else Decimal("0.000000")
        )
    if account.expected_annual_yield is not None:
        return account.expected_annual_yield
    if account.account_kind == "liability":
        return Decimal("0.000000")
    return DEFAULT_CATEGORY_RETURNS.get(account.category, DEFAULT_FALLBACK_RETURN)


def period_return(annual_return: Decimal, months_per_period: int) -> Decimal:
    """Convert an effective annual return to an effective period return."""
    if months_per_period == 12:
        return annual_return
    return (Decimal("1") + annual_return) ** (Decimal(months_per_period) / Decimal("12")) - Decimal(
        "1"
    )


def project_balance_with_return(
    balance: Decimal,
    annual_return: Decimal,
    months_per_period: int,
) -> Decimal:
    return (balance * (Decimal("1") + period_return(annual_return, months_per_period))).quantize(
        Decimal("0.01")
    )
