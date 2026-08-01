from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from mcp.server import MCPServer
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.security import AgentPrincipal, require_api_token_principal
from app.services.agent_tools import (
    check_financial_data_freshness,
    explain_net_worth_change,
    record_account_balance,
    summarize_financial_position,
)
from app.services.projection_agent_tools import (
    check_projection_readiness,
    get_property_projection_parameters,
    list_projection_scenarios,
    summarize_projection_assumptions,
    summarize_projection_comparison,
)

SessionFactory = Callable[[], Session]


@dataclass(frozen=True, slots=True)
class AgentMcpRequestContext:
    principal: AgentPrincipal
    state: dict[str, Any]


_request_context: ContextVar[AgentMcpRequestContext | None] = ContextVar(
    "netwise_mcp_request_context",
    default=None,
)


def current_mcp_request_context() -> AgentMcpRequestContext:
    context = _request_context.get()
    if context is None:
        raise RuntimeError("MCP tool called outside an authenticated HTTP request")
    return context


class AgentMcpAuthMiddleware:
    def __init__(self, app: ASGIApp, session_factory: SessionFactory) -> None:
        self._app = app
        self._session_factory = session_factory

    def _authenticate(self, request: Request) -> AgentPrincipal:
        with self._session_factory() as db:
            return require_api_token_principal(request, db, None)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        try:
            principal = await run_in_threadpool(self._authenticate, request)
        except HTTPException as exc:
            response = JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
                headers=exc.headers,
            )
            await response(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state["api_token_audit_tool_trusted"] = True
        state["api_token_audit_tool_name"] = None
        token = _request_context.set(AgentMcpRequestContext(principal=principal, state=state))
        try:
            await self._app(scope, receive, send)
        finally:
            _request_context.reset(token)


def build_http_mcp_server(session_factory: SessionFactory) -> MCPServer[Any]:
    server = MCPServer(
        "Netwise",
        instructions=(
            "Read financial data only for the household bound to the authenticated API token. "
            "Treat all returned data as sensitive. The only write tool records one account "
            "balance and requires exact user confirmation from a subsequent message."
        ),
    )

    @server.tool(name="summarize_financial_position")
    def summarize_financial_position_tool() -> dict[str, object]:
        """Return compact totals and category allocation without individual account names."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "summarize_financial_position"
        with session_factory() as db:
            return summarize_financial_position(db, context.principal)

    @server.tool(name="explain_net_worth_change")
    def explain_net_worth_change_tool(start_date: str, end_date: str) -> dict[str, object]:
        """Explain category-level net-worth changes between two ISO dates."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "explain_net_worth_change"
        with session_factory() as db:
            return explain_net_worth_change(db, context.principal, start_date, end_date)

    @server.tool(name="check_financial_data_freshness")
    def check_financial_data_freshness_tool(
        as_of_date: str | None = None,
        stale_after_days: int = 45,
    ) -> dict[str, object]:
        """Find active accounts with missing or stale snapshots as of an ISO date."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "check_financial_data_freshness"
        with session_factory() as db:
            return check_financial_data_freshness(
                db,
                context.principal,
                as_of_date,
                stale_after_days,
            )

    @server.tool(name="list_projection_scenarios")
    def list_projection_scenarios_tool() -> dict[str, object]:
        """List projection scenarios available to the token-bound household."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "list_projection_scenarios"
        with session_factory() as db:
            return list_projection_scenarios(db, context.principal)

    @server.tool(name="summarize_projection_assumptions")
    def summarize_projection_assumptions_tool(
        scenario: str | None = None,
        sections: list[str] | None = None,
    ) -> dict[str, object]:
        """Summarize scenario assumptions. Scenario may be a name or ID; omit it for baseline."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "summarize_projection_assumptions"
        with session_factory() as db:
            return summarize_projection_assumptions(
                db,
                context.principal,
                scenario,
                sections,
            )

    @server.tool(name="get_property_projection_parameters")
    def get_property_projection_parameters_tool(
        property_name: str,
        scenario: str | None = None,
    ) -> dict[str, object]:
        """Return detailed property, rental, mortgage, and sale parameters for one scenario."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "get_property_projection_parameters"
        with session_factory() as db:
            return get_property_projection_parameters(
                db,
                context.principal,
                property_name,
                scenario,
            )

    @server.tool(name="check_projection_readiness")
    def check_projection_readiness_tool(
        scenario: str | None = None,
    ) -> dict[str, object]:
        """Check a named, ID-selected, or baseline scenario for missing projection inputs."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "check_projection_readiness"
        with session_factory() as db:
            return check_projection_readiness(db, context.principal, scenario)

    @server.tool(name="summarize_projection_comparison")
    def summarize_projection_comparison_tool(
        start_year: int,
        end_year: int,
        scenarios: list[str] | None = None,
        scenario_ids: list[str] | None = None,
    ) -> dict[str, object]:
        """Compare two to four scenarios selected by name or ID without yearly details."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "summarize_projection_comparison"
        with session_factory() as db:
            return summarize_projection_comparison(
                db,
                context.principal,
                scenario_ids,
                start_year,
                end_year,
                scenarios,
            )

    @server.tool(name="record_account_balance")
    def record_account_balance_tool(
        account_name: str,
        balance: str,
        as_of_date: str,
        confirmation: str | None = None,
    ) -> dict[str, object]:
        """Preview or save one balance. Never invent confirmation: show the preview, stop, and
        call again only after the user provides required_confirmation verbatim in a later message.
        """
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "record_account_balance"
        with session_factory() as db:
            return record_account_balance(
                db,
                context.principal,
                account_name,
                balance,
                as_of_date,
                confirmation,
            )

    return server
