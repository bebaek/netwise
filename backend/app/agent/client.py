from collections.abc import Mapping
from typing import Any

import httpx


class NetwiseApiError(RuntimeError):
    """A safe-to-report failure returned by the Netwise API."""


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
    ) -> Any:
        try:
            response = self._client.request(method, path.lstrip("/"), params=params, json=json)
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

    def get_household(self) -> dict[str, Any]:
        if self._household is None:
            households = self._request("GET", "/households")
            if not isinstance(households, list) or len(households) != 1:
                raise NetwiseApiError(
                    "The API token must resolve to exactly one household"
                )
            household = households[0]
            if not isinstance(household, dict) or not isinstance(household.get("id"), str):
                raise NetwiseApiError("Netwise returned invalid household data")
            self._household = household
        return self._household

    @property
    def household_id(self) -> str:
        return self.get_household()["id"]

    def get_financial_summary(self) -> dict[str, Any]:
        return self._request("GET", f"/dashboard/{self.household_id}/net-worth")

    def list_accounts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/accounts", params={"household_id": self.household_id})

    def list_recent_balances(self, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return self._request(
            "GET",
            f"/households/{self.household_id}/snapshots",
            params={"limit": limit},
        )

    def get_net_worth_history(self) -> dict[str, Any]:
        return self._request("GET", f"/dashboard/{self.household_id}/net-worth/history")

    def list_projection_scenarios(self) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/projection-scenarios",
            params={"household_id": self.household_id},
        )

    def compare_projection_scenarios(
        self,
        scenario_ids: list[str],
        start_year: int,
        end_year: int,
    ) -> dict[str, Any]:
        if not 2 <= len(scenario_ids) <= 4:
            raise ValueError("Choose between two and four projection scenarios")
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("Projection scenario IDs must be unique")
        if start_year > end_year:
            raise ValueError("start_year must not be after end_year")
        return self._request(
            "POST",
            f"/dashboard/{self.household_id}/projection-comparison",
            json={
                "scenario_ids": scenario_ids,
                "start_year": start_year,
                "end_year": end_year,
                "interval": "annual",
            },
        )
