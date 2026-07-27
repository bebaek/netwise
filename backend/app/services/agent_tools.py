from datetime import date
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.net_worth import calculate_net_worth, calculate_net_worth_breakdown_history
from app.core.security import AgentPrincipal, require_agent_scopes
from app.db.models import Account, BalanceSnapshot, Household
from app.services.balance_snapshots import BalanceSnapshotValue, save_snapshot_batch


def _money(value: object) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def _iso_date(value: str | None, field_name: str) -> date:
    if not value:
        raise ValueError(f"{field_name} is required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD)") from exc


def _date_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _require_household(db: Session, principal: AgentPrincipal) -> None:
    if db.get(Household, principal.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")


def summarize_financial_position(db: Session, principal: AgentPrincipal) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read")
    _require_household(db, principal)

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


def explain_net_worth_change(
    db: Session,
    principal: AgentPrincipal,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read")
    _require_household(db, principal)
    requested_start = _iso_date(start_date, "start_date")
    requested_end = _iso_date(end_date, "end_date")
    if requested_start > requested_end:
        raise ValueError("start_date must not be after end_date")

    history = calculate_net_worth_breakdown_history(db, principal.household_id)
    dated_points = sorted(
        ((point["as_of_date"], point) for point in history["points"]),
        key=lambda item: item[0],
    )
    start_point = next(
        (point for point_date, point in reversed(dated_points) if point_date <= requested_start),
        None,
    )
    end_point = next(
        (point for point_date, point in reversed(dated_points) if point_date <= requested_end),
        None,
    )
    if start_point is None or end_point is None:
        raise ValueError("No balance history is available on or before one of the requested dates")

    category_changes: list[dict[str, object]] = []
    for account_kind, field, effect_multiplier in (
        ("asset", "asset_categories", Decimal("1")),
        ("liability", "liability_categories", Decimal("-1")),
    ):
        start_categories = {
            str(row["category"]): Decimal(str(row["balance"])) for row in start_point[field]
        }
        end_categories = {
            str(row["category"]): Decimal(str(row["balance"])) for row in end_point[field]
        }
        for category in sorted(start_categories.keys() | end_categories.keys()):
            balance_change = end_categories.get(category, Decimal("0")) - start_categories.get(
                category, Decimal("0")
            )
            if balance_change == 0:
                continue
            category_changes.append(
                {
                    "account_kind": account_kind,
                    "category": category,
                    "balance_change": _money(balance_change),
                    "net_worth_effect": _money(balance_change * effect_multiplier),
                }
            )
    category_changes.sort(
        key=lambda item: abs(Decimal(str(item["net_worth_effect"]))),
        reverse=True,
    )

    start_net_worth = Decimal(str(start_point["net_worth"]))
    end_net_worth = Decimal(str(end_point["net_worth"]))
    return {
        "requested_period": {"start_date": start_date, "end_date": end_date},
        "actual_period": {
            "start_date": _date_string(start_point["as_of_date"]),
            "end_date": _date_string(end_point["as_of_date"]),
        },
        "starting_net_worth": _money(start_net_worth),
        "ending_net_worth": _money(end_net_worth),
        "net_worth_change": _money(end_net_worth - start_net_worth),
        "assets_change": _money(
            Decimal(str(end_point["assets_total"])) - Decimal(str(start_point["assets_total"]))
        ),
        "liabilities_change": _money(
            Decimal(str(end_point["liabilities_total"]))
            - Decimal(str(start_point["liabilities_total"]))
        ),
        "category_changes": category_changes,
    }


def check_financial_data_freshness(
    db: Session,
    principal: AgentPrincipal,
    as_of_date: str | None = None,
    stale_after_days: int = 45,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read")
    _require_household(db, principal)
    if not 1 <= stale_after_days <= 3650:
        raise ValueError("stale_after_days must be between 1 and 3650")
    effective_date = _iso_date(as_of_date, "as_of_date") if as_of_date else date.today()
    accounts = list(
        db.scalars(
            select(Account)
            .where(
                Account.household_id == principal.household_id,
                Account.is_active.is_(True),
            )
            .order_by(Account.name)
        ).all()
    )

    missing_accounts: list[dict[str, object]] = []
    stale_accounts: list[dict[str, object]] = []
    current_count = 0
    for account in accounts:
        latest_date = db.scalar(
            select(BalanceSnapshot.as_of_date)
            .where(BalanceSnapshot.account_id == account.id)
            .order_by(BalanceSnapshot.as_of_date.desc(), BalanceSnapshot.created_at.desc())
            .limit(1)
        )
        account_summary = {"account_id": str(account.id), "account_name": account.name}
        if latest_date is None:
            missing_accounts.append(account_summary)
            continue
        age_days = (effective_date - latest_date).days
        if age_days > stale_after_days:
            stale_accounts.append(
                {
                    **account_summary,
                    "latest_snapshot_date": latest_date.isoformat(),
                    "age_days": age_days,
                }
            )
        else:
            current_count += 1

    stale_accounts.sort(key=lambda item: int(item["age_days"]), reverse=True)
    return {
        "as_of_date": effective_date.isoformat(),
        "stale_after_days": stale_after_days,
        "account_counts": {
            "active": len(accounts),
            "current": current_count,
            "stale": len(stale_accounts),
            "missing": len(missing_accounts),
        },
        "stale_accounts": stale_accounts,
        "missing_accounts": missing_accounts,
    }


def record_account_balance(
    db: Session,
    principal: AgentPrincipal,
    account_name: str,
    balance: str,
    as_of_date: str,
    confirmation: str | None = None,
) -> dict[str, object]:
    require_agent_scopes(principal, "finance:read", "finance:write")
    _require_household(db, principal)
    normalized_name = account_name.strip()
    if not normalized_name:
        raise ValueError("account_name is required")
    snapshot_date = _iso_date(as_of_date, "as_of_date")
    if snapshot_date > date.today():
        raise ValueError("as_of_date must not be in the future")

    try:
        balance_value = Decimal(balance)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("balance must be a finite monetary value") from exc
    if not balance_value.is_finite():
        raise ValueError("balance must be a finite monetary value")
    if balance_value.as_tuple().exponent < -2:
        raise ValueError("balance must have at most two decimal places")
    if abs(balance_value) >= Decimal("10000000000000000"):
        raise ValueError("balance is too large")
    normalized_balance = _money(balance_value)
    canonical_date = snapshot_date.isoformat()

    accounts = list(
        db.scalars(
            select(Account)
            .where(Account.household_id == principal.household_id)
            .order_by(Account.name)
            .with_for_update()
        ).all()
    )
    matches = [
        account
        for account in accounts
        if account.name.strip().casefold() == normalized_name.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(
            "account_name must identify exactly one account; use list_accounts to choose it"
        )
    account = matches[0]
    if not account.is_active:
        raise ValueError("Cannot record a balance for an inactive account")

    existing = db.scalars(
        select(BalanceSnapshot)
        .where(
            BalanceSnapshot.account_id == account.id,
            BalanceSnapshot.as_of_date == snapshot_date,
        )
        .with_for_update()
        .limit(1)
    ).first()
    existing_balance = _money(existing.balance) if existing is not None else None
    action = "update" if existing is not None else "create"
    confirmation_parts = [
        "CONFIRM",
        action.upper(),
        account.name,
        canonical_date,
        normalized_balance,
        account.currency.upper(),
    ]
    if existing_balance is not None:
        confirmation_parts.extend(["REPLACING", existing_balance])
    required_confirmation = " ".join(confirmation_parts)

    preview = {
        "status": "confirmation_required",
        "action": action,
        "account_name": account.name,
        "as_of_date": canonical_date,
        "balance": normalized_balance,
        "currency": account.currency.upper(),
        "existing_balance": existing_balance,
        "required_confirmation": required_confirmation,
        "instruction": (
            "Show this preview to the user and ask them to reply with the exact confirmation "
            "text. Do not call this tool again until the user supplies it verbatim in a "
            "subsequent message."
        ),
    }
    if confirmation != required_confirmation:
        return preview

    saved = save_snapshot_batch(
        db,
        principal.household_id,
        as_of_date=snapshot_date,
        currency=account.currency.upper(),
        source="manual",
        confidence_level="confirmed_by_user",
        snapshots=[BalanceSnapshotValue(account_id=account.id, balance=balance_value)],
    )
    return {
        "status": "saved",
        "action": action,
        "account_name": account.name,
        "as_of_date": canonical_date,
        "balance": normalized_balance,
        "currency": account.currency.upper(),
        "created_count": saved["created_count"],
        "updated_count": saved["updated_count"],
    }
