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


def test_mcp_server_registers_read_only_semantic_tools():
    client = NetwiseApiClient("https://netwise.example", "secret-token")
    try:
        server = build_server(client)
        tools = asyncio.run(server.list_tools())
    finally:
        client.close()

    assert {tool.name for tool in tools} == {
        "get_financial_summary",
        "get_net_worth_history",
        "list_accounts",
        "list_projection_scenarios",
        "list_recent_balances",
        "compare_projection_scenarios",
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
