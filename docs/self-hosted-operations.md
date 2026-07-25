# Self-Hosted Operations

## Goals

Netwise should be easy to operate for an individual, couple, family, or small trusted group.

Operational priorities:

- Simple setup
- Clear configuration
- Reliable backups
- Easy upgrades
- No required telemetry
- Data portability
- Secure defaults

## Deployment modes

Current repository targets:

1. Local development with `docker-compose.yml`
2. Initial Docker Compose production deployment with `compose.production.yml`
3. Kubernetes deployment with Helm (planned)

The production Compose path is the supported small-host boundary. It publishes
only the Nginx frontend, keeps the backend and PostgreSQL unpublished, disables
public signup and administrative tools, enables secure authentication cookies,
and uses a dedicated one-shot migration service.

## Production Compose setup

`production.env.example` documents the non-secret production variables. Generate
the actual ignored environment file rather than using a committed password:

```bash
printf 'NETWISE_POSTGRES_PASSWORD=%s\nNETWISE_HTTP_BIND_ADDRESS=127.0.0.1\nNETWISE_HTTP_PORT=8080\n' \
  "$(openssl rand -hex 32)" > .env.production
chmod 600 .env.production
```

The password is restricted to hexadecimal characters so it can safely be
interpolated into the PostgreSQL connection URL. Compose rejects a missing or
empty password.

Build and migrate before the first startup:

```bash
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml run --rm migrate
docker compose --env-file .env.production -f compose.production.yml up -d --wait
```

The normal backend command starts only Uvicorn; it does not run Alembic. Run the
same migration command after building an upgraded image and before restarting
application services. Alembic migrations are transactional where PostgreSQL and
the migration operation permit it, but take a backup before every upgrade.

By default, the only published port is the frontend on
`127.0.0.1:${NETWISE_HTTP_PORT:-8080}`. Terminate HTTPS with a same-host reverse
proxy and forward traffic to that address. A minimal Caddy site is:

```caddyfile
finance.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Keep `NETWISE_HTTP_BIND_ADDRESS=127.0.0.1` for a same-host proxy. If TLS is
terminated on another host, protect the private network path before changing the
bind address. Production cookies use the `Secure` attribute and are not intended
for a plain-HTTP deployment.

Operational checks:

```bash
docker compose --env-file .env.production -f compose.production.yml ps
curl --fail https://finance.example.com/health/live
curl --fail https://finance.example.com/api/health/ready
```

Use `docker compose ... logs backend` and `docker compose ... logs frontend` for
local diagnostics. Do not paste `.env.production` or rendered Compose output into
issues because both contain the database password.

## Runtime services

Minimum services:

- Web frontend
- API backend
- PostgreSQL

Likely services after the first version:

- Background worker
- Redis
- Object storage compatible service or local file storage for exports and backups

## Configuration

The application reads implemented settings with the `NETWISE_` prefix. The
production Compose file fixes the security-sensitive defaults and derives
`NETWISE_DATABASE_URL` from the required `NETWISE_POSTGRES_PASSWORD`. Relevant
application variables are:

```text
NETWISE_DATABASE_URL=postgresql+psycopg://netwise:change-me@postgres:5432/netwise
NETWISE_PUBLIC_SIGNUP=false
NETWISE_SINGLE_HOUSEHOLD_MODE=true
NETWISE_ENABLE_ADMIN_TOOLS=false
NETWISE_IMPORT_ROOT=/import/fintrack
NETWISE_AUTH_COOKIE_NAME=netwise_session
NETWISE_AUTH_COOKIE_SECURE=true
NETWISE_AUTH_SESSION_DAYS=30
```

## Single-household mode

Single-household mode should simplify deployment for families and individuals.

Behavior:

- First registered user becomes owner.
- A default household is created automatically.
- Public signup can be disabled after setup.
- Invites can be owner-controlled.

## Backups

Backup requirements:

- Database backup command or container job.
- Full household JSON export from the app.
- Clear restore documentation.
- Upgrade notes that mention migration compatibility.

Recommended backup artifacts:

- PostgreSQL dump
- Application configuration, excluding secrets where possible
- Exported household JSON for portability

## Upgrades

Upgrades should run database migrations explicitly.

Preferred process:

1. Back up database.
2. Pull new container images.
3. Run migrations.
4. Start application services.
5. Verify health endpoint.

## Health checks

Current health endpoints:

- `/health/live`
- `/health/ready`

Readiness checks database connectivity.

## Security defaults

- Bind development ports to localhost unless remote access is explicitly required.
- Require HTTPS in production deployments.
- Do not enable public signup by default in self-hosted production examples.
- Keep administrative tools disabled by default. When FinTrack import is enabled, configure a dedicated read-only `NETWISE_IMPORT_ROOT`; requests outside that root are rejected.
- Do not enable plugins by default.
- Generate secure secret keys during setup.
- Avoid logging financial balances in application logs.
- Provide clear file permission guidance for secrets.

## Observability

Default observability should be minimal and local.

Useful outputs:

- Structured application logs
- Request IDs
- Migration logs
- Worker job logs
- Optional metrics endpoint later

## Data retention

Self-hosted operators control data retention. The app should provide tools to delete:

- Account snapshots
- Accounts
- Projection results
- Household exports
- User accounts
- Entire household data

## Initial deliverables

- `docker-compose.yml` for development
- `compose.production.yml` and `production.env.example` for production
- Explicit `migrate` Compose service
- Backup script (planned)
- Restore script (planned)
- Upgrade documentation (in progress)
- Helm chart after the Docker Compose path is stable
