# Netwise

Netwise is a privacy-conscious personal finance planning app focused on balance snapshots, asset categorization, and long-term projections without transaction tracking.

This repository contains the open-source, self-host-oriented application and is
licensed under the [Apache License 2.0](LICENSE).

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

## Implementation status

| Capability | Status |
| --- | --- |
| Authentication and household authorization | Implemented |
| Accounts, balance snapshots, and net-worth history | Implemented |
| Asset allocation and historical analytics | Implemented |
| Deterministic projections with income, tax, spending, and withdrawal policies | Implemented |
| Named projection scenarios with independent assumptions and two-to-four-scenario comparison | Implemented |
| Real-estate, mortgage, and property-sale planning | Implemented |
| FinTrack import and household JSON export | Implemented; local admin tools are disabled by default |
| Development and production Docker Compose deployments | Implemented |
| Production backup, restore, and upgrade procedures | Implemented |
| Automatic property-sale optimization | Experimental |
| Optional institution automation plugins | Planned |
| Advanced time-series and probabilistic projections | Planned |
| Kubernetes and Helm deployment | Planned |

## Deployment

Supported deployment paths:

- Local development with Docker Compose.
- Small production deployment with Docker Compose.

Kubernetes and Helm packaging is planned but not currently provided.

## Backend stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic

Redis-backed workers may be added when asynchronous jobs are needed.

## Development quickstart

The development stack starts a FastAPI backend, PostgreSQL database, and Vite frontend. From the repository root:

```bash
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

### Production Compose quickstart

The production Compose path builds the static Nginx frontend and exposes only
that frontend. PostgreSQL and the backend remain on internal container networks.
Create an ignored, owner-readable environment file with a generated database
password:

```bash
printf 'NETWISE_POSTGRES_PASSWORD=%s\nNETWISE_HTTP_BIND_ADDRESS=127.0.0.1\nNETWISE_HTTP_PORT=8080\n' \
  "$(openssl rand -hex 32)" > .env.production
chmod 600 .env.production
```

Build the images, run the one-shot migration job, and then start the application.
The backend image resolves production dependencies from `backend/uv.lock` with a
pinned uv release, and both frontend images install from `package-lock.json` with
`npm ci`:

```bash
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml run --rm migrate
docker compose --env-file .env.production -f compose.production.yml up -d --wait
```

The frontend is now available to a same-host HTTPS reverse proxy at
`http://127.0.0.1:8080`; its health endpoint is `/health/live`, and backend
readiness is available through `/api/health/ready`. Production authentication
cookies are marked secure, so put an HTTPS terminator such as Caddy, Nginx, or a
managed load balancer in front before using the application. Do not expose the
plain HTTP port directly to an untrusted network. See
[`docs/self-hosted-operations.md`](docs/self-hosted-operations.md) for the
service boundaries, backup and restore procedures, and safe upgrade ordering.

Create an owner-readable backup with a checksum, or perform a confirmed
destructive restore, using:

```bash
./scripts/backup-production.sh
./scripts/restore-production.sh backups/netwise-YYYYMMDDTHHMMSSZ.dump \
  --confirm-destroy-current-data
```

The standalone frontend image can also be built with:

```bash
docker build -f frontend/Dockerfile.production -t netwise-frontend:production frontend
```

It expects to share a container network with a service named `backend`. The
existing `docker compose up` command remains the development workflow.

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
(cd backend && uv run alembic upgrade head)
(cd backend && uv run --extra dev pytest -q)
```

Create future migrations after model changes:

```bash
(cd backend && uv run alembic revision --autogenerate -m "describe change")
```

Run frontend type checks and builds locally:

```bash
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run build
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

## Frontend stack

- React with TypeScript and Vite
- TanStack Query for server-state management
- Playwright for browser testing
- CSS-based responsive layouts and charts

## Documentation

- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Code Audit Improvement Roadmap](docs/code-audit-roadmap.md)
- [Product Design](docs/product-design.md)
- [Technical Design](docs/technical-design.md)
- [Projection Strategy Architecture](docs/projection-strategy-architecture.md)
- [Projection Scenarios API](docs/projection-scenarios-api.md)
- [Projection Scenarios Implementation Plan](docs/projection-scenarios-plan.md)
- [Property Sale Tax Strategy](docs/property-sale-tax-strategy.md)
- [Self-Hosted Operations](docs/self-hosted-operations.md)
- [Lessons from `fintrack`](docs/fintrack-lessons.md)

## License

Netwise is licensed under the [Apache License 2.0](LICENSE).
