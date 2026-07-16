from fastapi import FastAPI

from app.api.routes import accounts, dashboard, health, households


def create_app() -> FastAPI:
    app = FastAPI(title="Netwise API")

    app.include_router(health.router)
    app.include_router(households.router)
    app.include_router(accounts.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
