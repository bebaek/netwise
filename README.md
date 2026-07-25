# Netwise

Netwise is a privacy-conscious personal finance planning app focused on balance snapshots, asset categorization, and long-term projections without transaction tracking.

This repository contains the open-source, self-host-oriented application.

## Core idea

Netwise helps a household answer:

- What is our current financial status?
- How are our assets distributed across liquidity and retirement categories?
- How has our net worth changed over time?
- Where are our assets likely to be in future scenarios?

## Product principles

- Balance snapshots over transaction feeds.
- Manual-first data entry with guided institution navigation.
- Optional automation through clearly isolated plugins later.
- Household-oriented multi-user support.
- Data portability and transparent assumptions.
- Simple deterministic projections first; advanced time-series analysis later.

## Intended deployment

The project should be easy to run for an individual, couple, family, or small trusted group using container-based deployment.

Planned deployment options:

- Local development with Docker Compose.
- Small production deployment with Docker Compose.
- Advanced deployment with Kubernetes and Helm.

## Planned backend stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- Redis-backed workers when asynchronous jobs are needed

## Current development quickstart

The current skeleton starts a FastAPI backend, PostgreSQL database, and Vite frontend:

```bash
cd /Users/burm/code/netwise
cp .env.example .env
docker compose up --build
```

Open the frontend at:

```text
http://localhost:5173
```

On first launch, create the initial owner account with an email address and a password of at least 12 characters. The initial owner is attached to existing households during upgrades; a new single-household installation receives a default `Home` household. Later visits require sign-in, and application API routes reject unauthenticated requests.

The backend is available directly at:

```text
http://localhost:8001
```

Admin tools such as FinTrack import and household JSON export are disabled by default, including in the committed Docker Compose development setup. The published development ports bind to `127.0.0.1` rather than all host interfaces; the backend defaults to host port `8001` to avoid common port conflicts. Override development ports with `NETWISE_BACKEND_PORT`, `NETWISE_FRONTEND_PORT`, or `NETWISE_POSTGRES_PORT` when needed. Only enable administrative tools intentionally for a trusted local deployment.

Health checks:

```bash
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready
```

### Production frontend image

A production frontend image is available separately from the Vite development
container:

```bash
docker build -f frontend/Dockerfile.production -t netwise-frontend:production frontend
```

The multi-stage image installs the locked dependencies with `npm ci`, builds the
static Vite bundle, and serves it with Nginx on port 80. Nginx provides SPA route
fallback, proxies same-origin `/api/*` requests to `backend:8000`, caches hashed
assets immutably, and exposes `/health/live`. The image expects to share a
container network with a service named `backend`. It is currently a building
block for the production Compose path; continue using `docker compose up` for
the supported development workflow.

### Optional local Docker overrides

Keep machine-specific Docker Compose settings in `docker-compose.override.yml`. This file is ignored by git so local absolute paths and personal mounts are not committed.

To mount FinTrack export/import data for the importer:

```bash
cp docker-compose.override.example.yml docker-compose.override.yml
# Edit docker-compose.override.yml and replace /path/to/fintrack/data.
docker compose up --build
```

The example enables administrative tools, configures `/import/fintrack` as the only allowed import root, and mounts the host directory there read-only. Import requests may use `.` for the mounted root or a relative child directory; paths and symlinks that resolve outside the configured root are rejected.

Run backend tests and migrations locally:

```bash
cd /Users/burm/code/netwise/backend
uv run alembic upgrade head
uv run --extra dev pytest -q
```

Create future migrations after model changes:

```bash
cd /Users/burm/code/netwise/backend
uv run alembic revision --autogenerate -m "describe change"
```

Run frontend type checks and builds locally:

```bash
cd /Users/burm/code/netwise/frontend
npm install
npm run lint
npm run build
```

Run Chromium end-to-end checks in an isolated Docker Compose stack:

```bash
npm --prefix frontend run test:e2e
```

This command builds a separate `netwise-e2e` Compose project, creates a disposable PostgreSQL volume, seeds only that database, runs the desktop and mobile Playwright projects against `http://127.0.0.1:55173`, and removes the stack and volume afterward. On failure it prints recent container logs before cleanup. Set `NETWISE_E2E_KEEP=1` to retain the failed stack for inspection, or `NETWISE_E2E_PORT` to use another host port. The older `test:e2e:demo` name is retained as an alias for the same isolated workflow.

Use `npm --prefix frontend run test:e2e:local` only when intentionally testing an already-running application; it does not seed or isolate that application's data. Install the browser once with `cd frontend && npx playwright install chromium`. Generated screenshots, traces, and HTML reports are written to ignored test output directories.

Seed realistic demo data for manual testing:

```bash
docker compose exec backend python -m app.seed_demo --reset
```

The seed command creates a `Demo Household` with accounts, snapshots, real estate, mortgage, income, tax records, and future projection events. Sign in with `demo@netwise.local` and password `netwise-demo-password`. Omit `--reset` to reuse existing demo data without duplicating records; running the seed command resets the demo account password to this documented local-development value.

## Planned frontend stack

- React or Next.js
- Charting for net worth history, category breakdowns, and projections

## Documentation

- [Code Audit Improvement Roadmap](docs/code-audit-roadmap.md)
- [Product Design](docs/product-design.md)
- [Technical Design](docs/technical-design.md)
- [Projection Strategy Architecture](docs/projection-strategy-architecture.md)
- [Property Sale Tax Strategy](docs/property-sale-tax-strategy.md)
- [Self-Hosted Operations](docs/self-hosted-operations.md)
- [Lessons from `fintrack`](docs/fintrack-lessons.md)

## License

License is not chosen yet. This repository is intended to be open source.
