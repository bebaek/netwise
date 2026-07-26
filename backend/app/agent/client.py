from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx


class NetwiseApiError(RuntimeError):
    """A safe-to-report failure returned by the Netwise API."""


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise NetwiseApiError("Netwise returned an invalid monetary value") from exc


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date in YYYY-MM-DD format") from exc


class NetwiseApiClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Netwise API URL is required")
        if not token.strip():
            raise ValueError("Netwise API token is required")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout_seconds,
            transport=transport,
        )
        self._household: dict[str, Any] | None = None

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, object] | None = None,
        tool_name: str | None = None,
    ) -> Any:
        headers = {"X-Netwise-Agent-Tool": tool_name} if tool_name else None
        try:
            response = self._client.request(
                method,
                path.lstrip("/"),
                params=params,
                json=json,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            message = detail if isinstance(detail, str) else "Netwise rejected the request"
            raise NetwiseApiError(f"Netwise API error {exc.response.status_code}: {message}") from exc
        except httpx.HTTPError as exc:
            raise NetwiseApiError("Could not connect to the Netwise API") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise NetwiseApiError("Netwise returned an invalid JSON response") from exc

    def get_household(self, tool_name: str | None = None) -> dict[str, Any]:
        if self._household is None:
            households = self._request("GET", "/households", tool_name=tool_name)
            if not isinstance(households, list) or len(households) != 1:
                raise NetwiseApiError(
                    "The API token must resolve to exactly one household"
                )
            household = households[0]
            if not isinstance(household, dict) or not isinstance(household.get("id"), str):
                raise NetwiseApiError("Netwise returned invalid household data")
            self._household = household
        return self._household

    def household_id_for(self, tool_name: str) -> str:
        return self.get_household(tool_name)["id"]

    def get_financial_summary(
        self,
        tool_name: str = "get_financial_summary",
    ) -> dict[str, Any]:
        household_id = self.household_id_for(tool_name)
        return self._request(
            "GET",
            f"/dashboard/{household_id}/net-worth",
            tool_name=tool_name,
        )

    def summarize_financial_position(self) -> dict[str, Any]:
        tool_name = "summarize_financial_position"
        summary = self.get_financial_summary(tool_name)
        accounts = summary.get("accounts", [])
        if not isinstance(accounts, list):
            raise NetwiseApiError("Netwise returned invalid account summary data")

        category_totals: dict[tuple[str, str], Decimal] = {}
        accounts_with_balances = 0
        for account in accounts:
            if not isinstance(account, dict):
                continue
            balance = account.get("balance")
            if balance is None:
                continue
            accounts_with_balances += 1
            account_kind = str(account.get("account_kind", "unknown"))
            category = str(account.get("category", "other"))
            key = (account_kind, category)
            category_totals[key] = category_totals.get(key, Decimal("0")) + _decimal(balance)

        return {
            "household_id": summary.get("household_id"),
            "net_worth": summary.get("net_worth"),
            "assets_total": summary.get("assets_total"),
            "liabilities_total": summary.get("liabilities_total"),
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
        self,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        requested_start = _iso_date(start_date, "start_date")
        requested_end = _iso_date(end_date, "end_date")
        if requested_start > requested_end:
            raise ValueError("start_date must not be after end_date")

        tool_name = "explain_net_worth_change"
        history = self._request(
            "GET",
            f"/dashboard/{self.household_id_for(tool_name)}/breakdown-history",
            tool_name=tool_name,
        )
        points = history.get("points", []) if isinstance(history, dict) else []
        if not isinstance(points, list):
            raise NetwiseApiError("Netwise returned invalid net-worth history data")

        dated_points: list[tuple[date, dict[str, Any]]] = []
        for point in points:
            if isinstance(point, dict) and isinstance(point.get("as_of_date"), str):
                dated_points.append((date.fromisoformat(point["as_of_date"]), point))
        dated_points.sort(key=lambda item: item[0])
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

        category_changes: list[dict[str, Any]] = []
        for account_kind, field, effect_multiplier in (
            ("asset", "asset_categories", Decimal("1")),
            ("liability", "liability_categories", Decimal("-1")),
        ):
            start_categories = {
                str(row["category"]): _decimal(row["balance"])
                for row in start_point.get(field, [])
                if isinstance(row, dict) and "category" in row and "balance" in row
            }
            end_categories = {
                str(row["category"]): _decimal(row["balance"])
                for row in end_point.get(field, [])
                if isinstance(row, dict) and "category" in row and "balance" in row
            }
            for category in sorted(start_categories.keys() | end_categories.keys()):
                balance_change = end_categories.get(category, Decimal("0")) - start_categories.get(
                    category, Decimal("0")
                )
                if balance_change == 0:
                    continue
                net_worth_effect = balance_change * effect_multiplier
                category_changes.append(
                    {
                        "account_kind": account_kind,
                        "category": category,
                        "balance_change": _money(balance_change),
                        "net_worth_effect": _money(net_worth_effect),
                    }
                )
        category_changes.sort(
            key=lambda item: abs(_decimal(item["net_worth_effect"])),
            reverse=True,
        )

        start_net_worth = _decimal(start_point["net_worth"])
        end_net_worth = _decimal(end_point["net_worth"])
        return {
            "requested_period": {"start_date": start_date, "end_date": end_date},
            "actual_period": {
                "start_date": start_point["as_of_date"],
                "end_date": end_point["as_of_date"],
            },
            "starting_net_worth": _money(start_net_worth),
            "ending_net_worth": _money(end_net_worth),
            "net_worth_change": _money(end_net_worth - start_net_worth),
            "assets_change": _money(
                _decimal(end_point["assets_total"]) - _decimal(start_point["assets_total"])
            ),
            "liabilities_change": _money(
                _decimal(end_point["liabilities_total"])
                - _decimal(start_point["liabilities_total"])
            ),
            "category_changes": category_changes,
        }

    def summarize_projection_comparison(
        self,
        scenario_ids: list[str],
        start_year: int,
        end_year: int,
    ) -> dict[str, Any]:
        comparison = self.compare_projection_scenarios(
            scenario_ids,
            start_year,
            end_year,
            tool_name="summarize_projection_comparison",
        )
        scenarios = comparison.get("scenarios", [])
        if not isinstance(scenarios, list):
            raise NetwiseApiError("Netwise returned invalid projection comparison data")
        return {
            "household_id": comparison.get("household_id"),
            "start_year": comparison.get("start_year"),
            "end_year": comparison.get("end_year"),
            "scenarios": [
                {
                    "scenario_id": scenario.get("scenario_id"),
                    "scenario_name": scenario.get("scenario_name"),
                    "ending_net_worth": scenario.get("ending_net_worth"),
                    "lowest_net_worth": scenario.get("lowest_net_worth"),
                    "lowest_liquid_assets_total": scenario.get(
                        "lowest_liquid_assets_total"
                    ),
                    "cumulative_projected_income": scenario.get(
                        "cumulative_projected_income"
                    ),
                    "cumulative_projected_taxes": scenario.get(
                        "cumulative_projected_taxes"
                    ),
                    "cumulative_projected_spending": scenario.get(
                        "cumulative_projected_spending"
                    ),
                    "retirement_date": scenario.get("retirement_date"),
                    "first_unfunded_date": scenario.get("first_unfunded_date"),
                    "warnings": scenario.get("warnings", []),
                }
                for scenario in scenarios
                if isinstance(scenario, dict)
            ],
        }

    def check_financial_data_freshness(
        self,
        as_of_date: str | None = None,
        stale_after_days: int = 45,
    ) -> dict[str, Any]:
        if not 1 <= stale_after_days <= 3650:
            raise ValueError("stale_after_days must be between 1 and 3650")
        effective_date = _iso_date(as_of_date, "as_of_date") if as_of_date else date.today()
        tool_name = "check_financial_data_freshness"
        accounts = [
            account
            for account in self.list_accounts(tool_name)
            if account.get("is_active", True)
        ]
        missing_accounts: list[dict[str, Any]] = []
        stale_accounts: list[dict[str, Any]] = []
        current_count = 0
        for account in accounts:
            account_id = str(account.get("id", ""))
            snapshots = self._request(
                "GET",
                f"/accounts/{account_id}/snapshots",
                tool_name=tool_name,
            )
            if not isinstance(snapshots, list) or not snapshots:
                missing_accounts.append(
                    {"account_id": account_id, "account_name": account.get("name")}
                )
                continue
            snapshot_dates = [
                date.fromisoformat(str(snapshot["as_of_date"]))
                for snapshot in snapshots
                if isinstance(snapshot, dict) and snapshot.get("as_of_date")
            ]
            if not snapshot_dates:
                missing_accounts.append(
                    {"account_id": account_id, "account_name": account.get("name")}
                )
                continue
            latest_date = max(snapshot_dates)
            age_days = (effective_date - latest_date).days
            if age_days > stale_after_days:
                stale_accounts.append(
                    {
                        "account_id": account_id,
                        "account_name": account.get("name"),
                        "latest_snapshot_date": latest_date.isoformat(),
                        "age_days": age_days,
                    }
                )
            else:
                current_count += 1
        stale_accounts.sort(key=lambda item: item["age_days"], reverse=True)
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

    def list_accounts(
        self,
        tool_name: str = "list_accounts",
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/accounts",
            params={"household_id": self.household_id_for(tool_name)},
            tool_name=tool_name,
        )

    def record_account_balance(
        self,
        account_name: str,
        balance: str,
        as_of_date: str,
        confirmation: str | None = None,
    ) -> dict[str, Any]:
        """Preview or save one balance after verbatim user confirmation."""
        tool_name = "record_account_balance"
        normalized_name = account_name.strip()
        if not normalized_name:
            raise ValueError("account_name is required")
        snapshot_date = _iso_date(as_of_date, "as_of_date")
        if snapshot_date > date.today():
            raise ValueError("as_of_date must not be in the future")

        balance_value = _decimal(balance)
        if not balance_value.is_finite():
            raise ValueError("balance must be a finite monetary value")
        if balance_value.as_tuple().exponent < -2:
            raise ValueError("balance must have at most two decimal places")
        if abs(balance_value) >= Decimal("10000000000000000"):
            raise ValueError("balance is too large")
        normalized_balance = _money(balance_value)

        accounts = self.list_accounts(tool_name)
        if not isinstance(accounts, list):
            raise NetwiseApiError("Netwise returned invalid account data")
        matches = [
            account
            for account in accounts
            if isinstance(account, dict)
            and str(account.get("name", "")).strip().casefold() == normalized_name.casefold()
        ]
        if len(matches) != 1:
            raise ValueError(
                "account_name must identify exactly one account; use list_accounts to choose it"
            )
        account = matches[0]
        if not account.get("is_active", True):
            raise ValueError("Cannot record a balance for an inactive account")
        account_id = account.get("id")
        if not isinstance(account_id, str):
            raise NetwiseApiError("Netwise returned invalid account data")
        canonical_name = str(account.get("name", normalized_name))
        currency = str(account.get("currency", "USD")).upper()
        household_id = self.household_id_for(tool_name)

        snapshots = self._request(
            "GET",
            f"/households/{household_id}/snapshots",
            params={"account_id": account_id, "limit": 200},
            tool_name=tool_name,
        )
        if not isinstance(snapshots, list):
            raise NetwiseApiError("Netwise returned invalid snapshot data")
        existing = next(
            (
                snapshot
                for snapshot in snapshots
                if isinstance(snapshot, dict) and snapshot.get("as_of_date") == as_of_date
            ),
            None,
        )
        existing_balance = (
            _money(_decimal(existing["balance"]))
            if isinstance(existing, dict) and existing.get("balance") is not None
            else None
        )
        action = "update" if existing is not None else "create"
        confirmation_parts = [
            "CONFIRM",
            action.upper(),
            canonical_name,
            as_of_date,
            normalized_balance,
            currency,
        ]
        if existing_balance is not None:
            confirmation_parts.extend(["REPLACING", existing_balance])
        required_confirmation = " ".join(confirmation_parts)

        preview = {
            "status": "confirmation_required",
            "action": action,
            "account_name": canonical_name,
            "as_of_date": as_of_date,
            "balance": normalized_balance,
            "currency": currency,
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

        saved = self._request(
            "POST",
            f"/households/{household_id}/snapshot-batch",
            json={
                "as_of_date": as_of_date,
                "currency": currency,
                "source": "manual",
                "confidence_level": "confirmed_by_user",
                "snapshots": [{"account_id": account_id, "balance": normalized_balance}],
            },
            tool_name=tool_name,
        )
        if not isinstance(saved, dict):
            raise NetwiseApiError("Netwise returned invalid snapshot data")
        return {
            "status": "saved",
            "action": action,
            "account_name": canonical_name,
            "as_of_date": as_of_date,
            "balance": normalized_balance,
            "currency": currency,
            "created_count": saved.get("created_count"),
            "updated_count": saved.get("updated_count"),
        }

    def list_recent_balances(self, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        tool_name = "list_recent_balances"
        return self._request(
            "GET",
            f"/households/{self.household_id_for(tool_name)}/snapshots",
            params={"limit": limit},
            tool_name=tool_name,
        )

    def get_net_worth_history(self) -> dict[str, Any]:
        tool_name = "get_net_worth_history"
        return self._request(
            "GET",
            f"/dashboard/{self.household_id_for(tool_name)}/net-worth/history",
            tool_name=tool_name,
        )

    def list_projection_scenarios(self) -> list[dict[str, Any]]:
        tool_name = "list_projection_scenarios"
        return self._request(
            "GET",
            "/projection-scenarios",
            params={"household_id": self.household_id_for(tool_name)},
            tool_name=tool_name,
        )

    def compare_projection_scenarios(
        self,
        scenario_ids: list[str],
        start_year: int,
        end_year: int,
        tool_name: str = "compare_projection_scenarios",
    ) -> dict[str, Any]:
        if not 2 <= len(scenario_ids) <= 4:
            raise ValueError("Choose between two and four projection scenarios")
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("Projection scenario IDs must be unique")
        if start_year > end_year:
            raise ValueError("start_year must not be after end_year")
        return self._request(
            "POST",
            f"/dashboard/{self.household_id_for(tool_name)}/projection-comparison",
            json={
                "scenario_ids": scenario_ids,
                "start_year": start_year,
                "end_year": end_year,
                "interval": "annual",
            },
            tool_name=tool_name,
        )
