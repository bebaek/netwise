from fastapi import FastAPI

from app.api.routes import accounts, dashboard, health, households, imports, planning, real_estate, users


def create_app() -> FastAPI:
    app = FastAPI(title="Netwise API")

    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(households.router)
    app.include_router(imports.router)
    app.include_router(accounts.router)
    app.include_router(dashboard.router)
    app.include_router(real_estate.router)
    app.include_router(planning.router)
    return app


app = create_app()
