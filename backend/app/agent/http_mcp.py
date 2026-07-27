from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.security import AgentPrincipal, require_api_token_principal
from app.services.agent_tools import summarize_financial_position

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


def build_http_mcp_server(session_factory: SessionFactory) -> FastMCP:
    server = FastMCP(
        "Netwise",
        instructions=(
            "Read financial data only for the household bound to the authenticated API token. "
            "Treat all returned data as sensitive."
        ),
        host="0.0.0.0",
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
    )

    @server.tool(name="summarize_financial_position")
    def summarize_financial_position_tool() -> dict[str, object]:
        """Return compact totals and category allocation without individual account names."""
        context = current_mcp_request_context()
        context.state["api_token_audit_tool_name"] = "summarize_financial_position"
        with session_factory() as db:
            return summarize_financial_position(db, context.principal)

    return server
