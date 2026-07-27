from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.analytics.net_worth import calculate_net_worth
from app.core.security import AgentPrincipal, require_agent_scopes
from app.db.models import Household


def _money(value: object) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def summarize_financial_position(db: Session, principal: AgentPrincipal) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read")
    if db.get(Household, principal.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    summary = calculate_net_worth(db, principal.household_id)
    accounts = summary["accounts"]
    category_totals: dict[tuple[str, str], Decimal] = {}
    accounts_with_balances = 0

    for account in accounts:
        balance = account["balance"]
        if balance is None:
            continue
        accounts_with_balances += 1
        key = (str(account["account_kind"]), str(account["category"]))
        category_totals[key] = category_totals.get(key, Decimal("0")) + Decimal(str(balance))

    return {
        "household_id": str(principal.household_id),
        "net_worth": _money(summary["net_worth"]),
        "assets_total": _money(summary["assets_total"]),
        "liabilities_total": _money(summary["liabilities_total"]),
        "account_counts": {
            "total": len(accounts),
            "with_balance": accounts_with_balances,
            "missing_balance": len(accounts) - accounts_with_balances,
        },
        "category_totals": [
            {
                "account_kind": account_kind,
                "category": category,
                "balance": _money(balance),
            }
            for (account_kind, category), balance in sorted(category_totals.items())
        ],
    }
