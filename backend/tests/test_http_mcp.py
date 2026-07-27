from sqlalchemy import select

from app.db.models import ApiTokenAuditEvent, Household
from mcp.types import LATEST_PROTOCOL_VERSION


def _register_and_create_token(client, db_session, scopes: list[str]) -> tuple[Household, str]:
    register = client.post(
        "/auth/register",
        json={
            "display_name": "MCP Owner",
            "email": "mcp@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert register.status_code == 201
    household = db_session.scalar(select(Household))
    created = client.post(
        "/api-tokens",
        json={
            "name": "HTTP MCP",
            "household_id": str(household.id),
            "scopes": scopes,
            "expires_in_days": 30,
        },
    )
    assert created.status_code == 201
    return household, created.json()["token"]


def _mcp_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _mcp_request(client, token: str, request_id: int, method: str, params: dict) -> dict:
    response = client.post(
        "/mcp",
        headers=_mcp_headers(token),
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_streamable_http_mcp_requires_a_valid_bearer_token(unauthenticated_client):
    registered = unauthenticated_client.post(
        "/auth/register",
        json={
            "display_name": "Cookie-only user",
            "email": "cookie-only@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert registered.status_code == 201
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "netwise-test", "version": "1"},
        },
    }

    missing = unauthenticated_client.post("/mcp", headers=_mcp_headers(), json=initialize)
    invalid = unauthenticated_client.post("/mcp", headers=_mcp_headers("invalid"), json=initialize)

    assert missing.status_code == 401
    assert missing.json()["detail"] == "Bearer token required"
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid or expired API token"


def test_streamable_http_mcp_enforces_tool_scopes(unauthenticated_client, db_session):
    _, token = _register_and_create_token(unauthenticated_client, db_session, ["finance:write"])
    unauthenticated_client.cookies.clear()

    called = _mcp_request(
        unauthenticated_client,
        token,
        1,
        "tools/call",
        {"name": "summarize_financial_position", "arguments": {}},
    )

    assert called["result"]["isError"] is True
    assert "API token scope does not permit this action" in str(called["result"]["content"])


def test_streamable_http_mcp_enforces_projection_tool_scope(unauthenticated_client, db_session):
    _, token = _register_and_create_token(unauthenticated_client, db_session, ["finance:read"])
    unauthenticated_client.cookies.clear()

    called = _mcp_request(
        unauthenticated_client,
        token,
        1,
        "tools/call",
        {
            "name": "summarize_projection_comparison",
            "arguments": {
                "scenario_ids": [
                    "11111111-1111-1111-1111-111111111111",
                    "22222222-2222-2222-2222-222222222222",
                ],
                "start_year": 2026,
                "end_year": 2030,
            },
        },
    )

    assert called["result"]["isError"] is True
    assert "API token scope does not permit this action" in str(called["result"]["content"])


def test_streamable_http_mcp_lists_and_calls_household_scoped_summary(
    unauthenticated_client, db_session
):
    household, token = _register_and_create_token(
        unauthenticated_client, db_session, ["finance:read"]
    )
    account_response = unauthenticated_client.post(
        "/accounts",
        json={
            "household_id": str(household.id),
            "name": "Private checking name",
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "currency": "USD",
        },
    )
    assert account_response.status_code == 201
    snapshot_response = unauthenticated_client.post(
        f"/households/{household.id}/snapshot-batch",
        json={
            "as_of_date": "2026-07-27",
            "source": "manual",
            "confidence_level": "confirmed_by_user",
            "snapshots": [{"account_id": account_response.json()["id"], "balance": "1234.56"}],
        },
    )
    assert snapshot_response.status_code == 201
    later_snapshot_response = unauthenticated_client.post(
        f"/households/{household.id}/snapshot-batch",
        json={
            "as_of_date": "2026-08-27",
            "source": "manual",
            "confidence_level": "confirmed_by_user",
            "snapshots": [{"account_id": account_response.json()["id"], "balance": "1500.00"}],
        },
    )
    assert later_snapshot_response.status_code == 201
    unauthenticated_client.cookies.clear()

    initialized = _mcp_request(
        unauthenticated_client,
        token,
        1,
        "initialize",
        {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "netwise-test", "version": "1"},
        },
    )
    listed = _mcp_request(unauthenticated_client, token, 2, "tools/list", {})
    called = _mcp_request(
        unauthenticated_client,
        token,
        3,
        "tools/call",
        {"name": "summarize_financial_position", "arguments": {}},
    )

    explained = _mcp_request(
        unauthenticated_client,
        token,
        4,
        "tools/call",
        {
            "name": "explain_net_worth_change",
            "arguments": {"start_date": "2026-07-27", "end_date": "2026-08-27"},
        },
    )
    freshness = _mcp_request(
        unauthenticated_client,
        token,
        5,
        "tools/call",
        {
            "name": "check_financial_data_freshness",
            "arguments": {"as_of_date": "2026-10-20", "stale_after_days": 45},
        },
    )

    assert initialized["result"]["serverInfo"]["name"] == "Netwise"
    assert [tool["name"] for tool in listed["result"]["tools"]] == [
        "summarize_financial_position",
        "explain_net_worth_change",
        "check_financial_data_freshness",
        "summarize_projection_comparison",
    ]
    assert all(
        "household_id" not in tool["inputSchema"].get("properties", {})
        for tool in listed["result"]["tools"]
    )
    assert called["result"]["isError"] is False
    assert called["result"]["structuredContent"] == {
        "household_id": str(household.id),
        "net_worth": "1500.00",
        "assets_total": "1500.00",
        "liabilities_total": "0.00",
        "account_counts": {"total": 1, "with_balance": 1, "missing_balance": 0},
        "category_totals": [{"account_kind": "asset", "category": "cash", "balance": "1500.00"}],
    }
    assert explained["result"]["structuredContent"]["net_worth_change"] == "265.44"
    assert explained["result"]["structuredContent"]["category_changes"] == [
        {
            "account_kind": "asset",
            "category": "cash",
            "balance_change": "265.44",
            "net_worth_effect": "265.44",
        }
    ]
    assert freshness["result"]["structuredContent"]["account_counts"] == {
        "active": 1,
        "current": 0,
        "stale": 1,
        "missing": 0,
    }
    assert freshness["result"]["structuredContent"]["stale_accounts"] == [
        {
            "account_id": account_response.json()["id"],
            "account_name": "Private checking name",
            "latest_snapshot_date": "2026-08-27",
            "age_days": 54,
        }
    ]
    assert "Private checking name" not in str(called)

    db_session.expire_all()
    events = list(
        db_session.scalars(select(ApiTokenAuditEvent).order_by(ApiTokenAuditEvent.created_at)).all()
    )
    assert events[-3].tool_name == "summarize_financial_position"
    assert events[-2].tool_name == "explain_net_worth_change"
    assert events[-1].path == "/mcp/"
    assert events[-1].tool_name == "check_financial_data_freshness"
