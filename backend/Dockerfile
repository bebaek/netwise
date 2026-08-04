FROM ghcr.io/astral-sh/uv:0.11.29 AS uv

FROM python:3.12-slim AS dependencies

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=dependencies /opt/venv /opt/venv
COPY app ./app
COPY logging.json ./
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config logging.json"]
