import asyncio
import json
import os
from pathlib import Path
import sys

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from app.agent.client import NetwiseApiClient, NetwiseApiError
from app.agent.mcp_server import build_server, client_from_environment


HOUSEHOLD_ID = "11111111-1111-1111-1111-111111111111"


def _json_response(payload, status_code=200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )


def test_agent_client_uses_bound_household_and_bearer_token():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer secret-token"
        if request.url.path == "/api/households":
            assert request.headers["X-Netwise-Agent-Tool"] == "get_financial_summary"
            return _json_response([{"id": HOUSEHOLD_ID, "name": "Home"}])
        if request.url.path == f"/api/dashboard/{HOUSEHOLD_ID}/net-worth":
            assert request.headers["X-Netwise-Agent-Tool"] == "get_financial_summary"
            return _json_response({"net_worth": "123.45"})
        if request.url.path == "/api/accounts":
            assert request.headers["X-Netwise-Agent-Tool"] == "list_accounts"
            assert request.url.params["household_id"] == HOUSEHOLD_ID
            return _json_response([{"id": "account-1", "name": "Checking"}])
        raise AssertionError(f"Unexpected request: {request.url}")

    client = NetwiseApiClient(
        "https://netwise.example/api",
        "secret-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.get_financial_summary() == {"net_worth": "123.45"}
        assert client.list_accounts() == [{"id": "account-1", "name": "Checking"}]
    finally:
        client.close()

    assert [request.url.path for request in requests].count("/api/households") == 1


def test_agent_client_lists_balances_and_compares_scenarios():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/households":
            return _json_response([{"id": HOUSEHOLD_ID, "name": "Home"}])
        if request.url.path == f"/households/{HOUSEHOLD_ID}/snapshots":
            assert request.headers["X-Netwise-Agent-Tool"] == "list_recent_balances"
            assert request.url.params["limit"] == "5"
            return _json_response([{"balance": "100.00"}])
        if request.url.path == f"/dashboard/{HOUSEHOLD_ID}/projection-comparison":
            assert request.headers["X-Netwise-Agent-Tool"] == "compare_projection_scenarios"
            assert request.method == "POST"
            assert json.loads(request.content) == {
                "scenario_ids": ["baseline", "retire-early"],
                "start_year": 2026,
                "end_year": 2050,
                "interval": "annual",
            }
            return _json_response({"scenarios": []})
        raise AssertionError(f"Unexpected request: {request.url}")

    client = NetwiseApiClient(
        "https://netwise.example",
        "secret-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.list_recent_balances(5) == [{"balance": "100.00"}]
        assert client.compare_projection_scenarios(
            ["baseline", "retire-early"], 2026, 2050
        ) == {"scenarios": []}
    finally:
        client.close()


@pytest.mark.parametrize("limit", [0, 101])
def test_agent_client_validates_balance_limit(limit):
    client = NetwiseApiClient("https://netwise.example", "secret-token")
    try:
        with pytest.raises(ValueError, match="between 1 and 100"):
            client.list_recent_balances(limit)
    finally:
        client.close()


def test_agent_client_reports_safe_api_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"detail": "API token scope does not permit this action"}, 403)

    client = NetwiseApiClient(
        "https://netwise.example",
        "secret-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(NetwiseApiError, match="API token scope does not permit"):
            client.get_financial_summary()
    finally:
        client.close()


def test_semantic_financial_summary_omits_account_names():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Netwise-Agent-Tool"] == "summarize_financial_position"
        if request.url.path == "/households":
            return _json_response([{"id": HOUSEHOLD_ID, "name": "Home"}])
        if request.url.path == f"/dashboard/{HOUSEHOLD_ID}/net-worth":
            return _json_response(
                {
                    "household_id": HOUSEHOLD_ID,
                    "net_worth": "215000.00",
                    "assets_total": "250000.00",
                    "liabilities_total": "35000.00",
                    "accounts": [
                        {
                            "name": "Private checking name",
                            "account_kind": "asset",
                            "category": "cash",
                            "balance": "50000.00",
                        },
                        {
                            "name": "Private brokerage name",
                            "account_kind": "asset",
                            "category": "taxable_investment",
                            "balance": "200000.00",
                        },
                        {
                            "name": "Private loan name",
                            "account_kind": "liability",
                            "category": "loan",
                            "balance": "35000.00",
                        },
                        {
                            "name": "Missing balance name",
                            "account_kind": "asset",
                            "category": "cash",
                            "balance": None,
                        },
                    ],
                }
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    client = NetwiseApiClient(
        "https://netwise.example",
        "secret-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.summarize_financial_position()
    finally:
        client.close()

    assert result["account_counts"] == {"total": 4, "with_balance": 3, "missing_balance": 1}
    assert result["category_totals"] == [
        {"account_kind": "asset", "category": "cash", "balance": "50000.00"},
        {
            "account_kind": "asset",
            "category": "taxable_investment",
            "balance": "200000.00",
        },
        {"account_kind": "liability", "category": "loan", "balance": "35000.00"},
    ]
    assert "Private" not in str(result)


def test_semantic_net_worth_change_ranks_category_effects():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Netwise-Agent-Tool"] == "explain_net_worth_change"
        if request.url.path == "/households":
            return _json_response([{"id": HOUSEHOLD_ID, "name": "Home"}])
        if request.url.path == f"/dashboard/{HOUSEHOLD_ID}/breakdown-history":
            return _json_response(
                {
                    "points": [
                        {
                            "as_of_date": "2026-01-31",
                            "net_worth": "150000.00",
                            "assets_total": "200000.00",
                            "liabilities_total": "50000.00",
                            "asset_categories": [
                                {"category": "cash", "balance": "50000.00"},
                                {"category": "retirement", "balance": "150000.00"},
                            ],
                            "liability_categories": [
                                {"category": "mortgage", "balance": "50000.00"}
                            ],
                        },
                        {
                            "as_of_date": "2026-06-30",
                            "net_worth": "175000.00",
                            "assets_total": "220000.00",
                            "liabilities_total": "45000.00",
                            "asset_categories": [
                                {"category": "cash", "balance": "45000.00"},
                                {"category": "retirement", "balance": "175000.00"},
                            ],
                            "liability_categories": [
                                {"category": "mortgage", "balance": "45000.00"}
                            ],
                        },
                    ]
                }
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    client = NetwiseApiClient(
        "https://netwise.example",
        "secret-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.explain_net_worth_change("2026-01-31", "2026-07-01")
    finally:
        client.close()

    assert result["actual_period"] == {
        "start_date": "2026-01-31",
        "end_date": "2026-06-30",
    }
    assert result["net_worth_change"] == "25000.00"
    assert result["category_changes"] == [
        {
            "account_kind": "asset",
            "category": "retirement",
            "balance_change": "25000.00",
            "net_worth_effect": "25000.00",
        },
        {
            "account_kind": "asset",
            "category": "cash",
            "balance_change": "-5000.00",
            "net_worth_effect": "-5000.00",
        },
        {
            "account_kind": "liability",
            "category": "mortgage",
            "balance_change": "-5000.00",
            "net_worth_effect": "5000.00",
        },
    ]


def test_semantic_projection_summary_omits_yearly_details():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Netwise-Agent-Tool"] == "summarize_projection_comparison"
        if request.url.path == "/households":
            return _json_response([{"id": HOUSEHOLD_ID, "name": "Home"}])
        if request.url.path == f"/dashboard/{HOUSEHOLD_ID}/projection-comparison":
            return _json_response(
                {
                    "household_id": HOUSEHOLD_ID,
                    "start_year": 2026,
                    "end_year": 2050,
                    "scenarios": [
                        {
                            "scenario_id": "baseline",
                            "scenario_name": "Baseline",
                            "ending_net_worth": "900000.00",
                            "lowest_net_worth": "150000.00",
                            "lowest_liquid_assets_total": "50000.00",
                            "cumulative_projected_income": "1000000.00",
                            "cumulative_projected_taxes": "200000.00",
                            "cumulative_projected_spending": "700000.00",
                            "retirement_date": "2040-01-01",
                            "first_unfunded_date": None,
                            "warnings": [],
                            "points": [{"accounts": [{"name": "Private account"}]}],
                        }
                    ],
                }
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    client = NetwiseApiClient(
        "https://netwise.example",
        "secret-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.summarize_projection_comparison(
            ["baseline", "alternative"], 2026, 2050
        )
    finally:
        client.close()

    assert result["scenarios"][0]["ending_net_worth"] == "900000.00"
    assert "points" not in result["scenarios"][0]
    assert "Private account" not in str(result)


def test_financial_data_freshness_reports_stale_and_missing_accounts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Netwise-Agent-Tool"] == "check_financial_data_freshness"
        if request.url.path == "/households":
            return _json_response([{"id": HOUSEHOLD_ID, "name": "Home"}])
        if request.url.path == "/accounts":
            return _json_response(
                [
                    {"id": "current", "name": "Current", "is_active": True},
                    {"id": "stale", "name": "Stale", "is_active": True},
                    {"id": "missing", "name": "Missing", "is_active": True},
                    {"id": "inactive", "name": "Inactive", "is_active": False},
                ]
            )
        if request.url.path == "/accounts/current/snapshots":
            return _json_response([{"as_of_date": "2026-07-20"}])
        if request.url.path == "/accounts/stale/snapshots":
            return _json_response([{"as_of_date": "2026-01-01"}])
        if request.url.path == "/accounts/missing/snapshots":
            return _json_response([])
        raise AssertionError(f"Unexpected request: {request.url}")

    client = NetwiseApiClient(
        "https://netwise.example",
        "secret-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.check_financial_data_freshness("2026-07-26", 45)
    finally:
        client.close()

    assert result["account_counts"] == {"active": 3, "current": 1, "stale": 1, "missing": 1}
    assert result["stale_accounts"][0]["account_name"] == "Stale"
    assert result["stale_accounts"][0]["age_days"] == 206
    assert result["missing_accounts"] == [
        {"account_id": "missing", "account_name": "Missing"}
    ]


def test_mcp_server_registers_read_only_semantic_tools():
    client = NetwiseApiClient("https://netwise.example", "secret-token")
    try:
        server = build_server(client)
        tools = asyncio.run(server.list_tools())
    finally:
        client.close()

    assert {tool.name for tool in tools} == {
        "check_financial_data_freshness",
        "compare_projection_scenarios",
        "explain_net_worth_change",
        "get_financial_summary",
        "get_net_worth_history",
        "list_accounts",
        "list_projection_scenarios",
        "list_recent_balances",
        "summarize_financial_position",
        "summarize_projection_comparison",
    }


async def _list_tools_over_stdio():
    backend_root = Path(__file__).resolve().parents[1]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.agent.mcp_server"],
        cwd=backend_root,
        env={**os.environ, "NETWISE_API_TOKEN": "test-token"},
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.list_tools()


def test_mcp_server_negotiates_stdio_transport():
    result = asyncio.run(_list_tools_over_stdio())
    assert "get_financial_summary" in {tool.name for tool in result.tools}


def test_mcp_environment_requires_token(monkeypatch):
    monkeypatch.delenv("NETWISE_API_TOKEN", raising=False)
    monkeypatch.setenv("NETWISE_API_URL", "https://netwise.example/api")

    with pytest.raises(RuntimeError, match="token is required"):
        client_from_environment()
