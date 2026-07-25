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

Build and migrate before the first startup. Container dependency installation is
lockfile-driven: the backend dependency stage runs pinned uv with
`uv sync --locked`, and frontend builds use `npm ci`.

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

Create a transaction-consistent PostgreSQL custom-format archive while the
application is running:

```bash
./scripts/backup-production.sh
```

The default destination is the ignored `backups/` directory. Pass a different
directory as the first argument for storage on a protected filesystem:

```bash
./scripts/backup-production.sh /srv/netwise/backups
```

Each run writes a timestamped `.dump` archive and a `.sha256` checksum using an
owner-only umask. The script starts only PostgreSQL if needed, validates the
archive with `pg_restore --list`, and never stops the application. The checksum
detects accidental corruption but does not authenticate or encrypt the backup.
Financial data in the archive is plaintext to anyone who can read it; encrypt
off-host copies and test retention and deletion policies appropriate to the
household.

Restore is deliberately destructive and requires an explicit confirmation flag:

```bash
./scripts/restore-production.sh \
  /srv/netwise/backups/netwise-YYYYMMDDTHHMMSSZ.dump \
  --confirm-destroy-current-data
```

Before changing the database, the restore script verifies the checksum when its
sidecar is present and validates the archive. It then stops frontend and backend
services, terminates remaining database sessions, drops and recreates the
`netwise` database from the archive, runs current migrations, and starts the
production stack with health checks. If restore or migration fails, application
services remain stopped for inspection.

Both scripts use `.env.production`, `compose.production.yml`, and the `netwise`
Compose project by default. Automation can override
`NETWISE_PRODUCTION_ENV_FILE`, `NETWISE_PRODUCTION_COMPOSE_FILE`, and
`NETWISE_PRODUCTION_PROJECT`. Set `NETWISE_PRODUCTION_ENV_FILE=-` only when all
required values are already supplied securely in the process environment.

Recommended backup artifacts:

- PostgreSQL custom-format dump and checksum
- The non-secret configuration template and a separately protected credential record
- Application-level household JSON exports when portability is required

## Upgrades

Use this order so a failed image build does not interrupt the running service and
a migration never races the old backend:

1. Create and retain a verified backup with `backup-production.sh`.
2. Fetch and check out the intended Netwise release.
3. Build the new images while the current containers continue running.
4. Stop frontend and backend services.
5. Run the one-shot migration job.
6. Start the stack and wait for health checks.
7. Verify both public health paths and representative application data.

```bash
./scripts/backup-production.sh /srv/netwise/backups
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml stop frontend backend
docker compose --env-file .env.production -f compose.production.yml run --rm migrate
docker compose --env-file .env.production -f compose.production.yml up -d --wait
curl --fail https://finance.example.com/health/live
curl --fail https://finance.example.com/api/health/ready
```

If image building fails, the old application remains running. If migration fails,
leave application services stopped and inspect the migration and PostgreSQL logs.
To roll back with a pre-upgrade archive, first restore the matching older
application checkout or images; otherwise `restore-production.sh` will correctly
apply migrations from the currently checked-out release after restoring.

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
- Multi-stage backend image built from `backend/uv.lock` with pinned uv
- Frontend images built from `package-lock.json` with `npm ci`
- Explicit `migrate` Compose service
- Exercised PostgreSQL backup and destructive restore scripts
- Upgrade documentation and rehearsal
- Helm chart after the Docker Compose path is stable
