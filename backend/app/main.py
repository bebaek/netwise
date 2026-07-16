from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import accounts, dashboard, health, households
from app.db import models  # noqa: F401 - ensure models are registered
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Skeleton convenience: create tables at startup until Alembic migrations are added.
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Netwise API", lifespan=lifespan)

    app.include_router(health.router)
    app.include_router(households.router)
    app.include_router(accounts.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
