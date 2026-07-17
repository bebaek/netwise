# Netwise

Netwise is a privacy-conscious personal finance planning app focused on balance snapshots, asset categorization, expense estimation, and long-term projections without transaction tracking.

This repository contains the open-source, self-host-oriented application.

## Core idea

Netwise helps a household answer:

- What is our current financial status?
- How are our assets distributed across liquidity and retirement categories?
- How has our net worth changed over time?
- What are our estimated living expenses without classifying every transaction?
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

Health checks:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

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

Run frontend type checks locally:

```bash
cd /Users/burm/code/netwise/frontend
npm install
npm run lint
npm run build
```

Seed realistic demo data for manual testing:

```bash
docker compose exec backend python -m app.seed_demo --reset
```

The seed command creates a `Demo Household` with accounts, snapshots, real estate, mortgage, income, tax records, and future projection events. Omit `--reset` to reuse existing demo data without duplicating records.

## Planned frontend stack

- React or Next.js
- Charting for net worth history, category breakdowns, and projections

## Documentation

- [Product Design](docs/product-design.md)
- [Technical Design](docs/technical-design.md)
- [Self-Hosted Operations](docs/self-hosted-operations.md)
- [Lessons from `fintrack`](docs/fintrack-lessons.md)

## License

License is not chosen yet. This repository is intended to be open source.
