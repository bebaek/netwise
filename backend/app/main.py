from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.agent.http_mcp import AgentMcpAuthMiddleware, SessionFactory, build_http_mcp_server
from app.api.routes import (
    accounts,
    api_tokens,
    auth,
    capabilities,
    dashboard,
    health,
    households,
    imports,
    planning,
    projection_scenarios,
    real_estate,
    users,
)
from app.core.audit import audit_api_token_request
from app.core.authorization import authorize_household_request
from app.core.security import require_authenticated_user
from app.db.session import SessionLocal


def create_app(session_factory: SessionFactory = SessionLocal) -> FastAPI:
    mcp_server = build_http_mcp_server(session_factory)
    mcp_app = mcp_server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with mcp_server.session_manager.run():
            yield

    app = FastAPI(title="Netwise API", lifespan=lifespan)
    app.state.audit_session_factory = session_factory
    app.middleware("http")(audit_api_token_request)

    app.include_router(health.router)
    app.include_router(capabilities.router)
    app.include_router(auth.router)
    app.include_router(api_tokens.router)
    authenticated = [Depends(require_authenticated_user)]
    household_authorized = [Depends(authorize_household_request)]
    app.include_router(users.router, dependencies=authenticated)
    app.include_router(households.router, dependencies=household_authorized)
    app.include_router(imports.router, dependencies=household_authorized)
    app.include_router(accounts.router, dependencies=household_authorized)
    app.include_router(dashboard.router, dependencies=household_authorized)
    app.include_router(real_estate.router, dependencies=household_authorized)
    app.include_router(planning.router, dependencies=household_authorized)
    app.include_router(projection_scenarios.router, dependencies=household_authorized)
    app.mount("/mcp", AgentMcpAuthMiddleware(mcp_app, session_factory), name="mcp")
    return app


app = create_app()
