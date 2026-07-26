from fastapi import Depends, FastAPI

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


def create_app() -> FastAPI:
    app = FastAPI(title="Netwise API")
    app.state.audit_session_factory = SessionLocal
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
    return app


app = create_app()
