import logging
from time import perf_counter
from typing import Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import ApiTokenAuditEvent

logger = logging.getLogger(__name__)


def _bounded_header(request: Request, name: str, max_length: int) -> str | None:
    value = request.headers.get(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized[:max_length] or None


def _tool_name(request: Request) -> str | None:
    if getattr(request.state, "api_token_audit_tool_trusted", False):
        value = getattr(request.state, "api_token_audit_tool_name", None)
        if isinstance(value, str):
            normalized = value.strip()
            return normalized[:100] or None
        return None
    return _bounded_header(request, "X-Netwise-Agent-Tool", 100)


async def audit_api_token_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started_at = perf_counter()
    session_factory = request.app.state.audit_session_factory
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        context = getattr(request.state, "api_token_audit_context", None)
        if context is not None:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            duration_ms = max(0, round((perf_counter() - started_at) * 1000))
            with session_factory() as db:
                try:
                    db.add(
                        ApiTokenAuditEvent(
                            **context,
                            method=request.method[:10],
                            path=str(path)[:500],
                            tool_name=_tool_name(request),
                            status_code=status_code,
                            duration_ms=duration_ms,
                        )
                    )
                    db.commit()
                except SQLAlchemyError:
                    db.rollback()
                    logger.exception("Could not record API token audit event")
