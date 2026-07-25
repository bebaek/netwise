# Contributing to Netwise

Thank you for helping improve Netwise.

## Development setup

From the repository root, copy the development environment template and start the Compose stack:

```bash
cp .env.example .env
docker compose up --build
```

Do not commit `.env` files, production database dumps, or real financial exports.

## Validation

Run backend checks:

```bash
(cd backend && uv sync --locked --extra dev)
(cd backend && uv run --no-sync ruff check app tests)
(cd backend && uv run --no-sync pytest -q)
```

Run frontend checks:

```bash
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run build
```

Run the isolated desktop browser suite when changing user-visible behavior:

```bash
npm --prefix frontend run test:e2e -- --project=desktop-chromium
```

## Pull requests

1. Create a focused branch from `main`.
2. Include tests for behavioral changes.
3. Update documentation when commands, configuration, or supported behavior changes.
4. Keep generated output, credentials, and personal financial data out of commits.
5. Open a pull request and wait for the required CI checks.

By submitting a contribution, you agree that it may be distributed under the repository's [Apache License 2.0](LICENSE).
