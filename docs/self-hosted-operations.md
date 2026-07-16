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

Supported targets planned for this repository:

1. Local development
2. Docker Compose production deployment
3. Kubernetes deployment with Helm

Docker Compose should be the first supported production path because it is the lowest-friction option for most users.

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

Configuration should be environment-variable based.

Example variables:

```text
NETWISE_DEPLOYMENT_MODE=self_hosted
NETWISE_PUBLIC_SIGNUP=false
NETWISE_SINGLE_HOUSEHOLD_MODE=true
NETWISE_DISABLE_TELEMETRY=true
NETWISE_ALLOW_LOCAL_AUTH=true
NETWISE_ENABLE_PLUGINS=false
DATABASE_URL=postgresql://netwise:netwise@postgres:5432/netwise
REDIS_URL=redis://redis:6379/0
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
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

Planned health endpoints:

- `/health/live`
- `/health/ready`

Readiness should check database connectivity and required service dependencies.

## Security defaults

- Require HTTPS in production deployments.
- Do not enable public signup by default in self-hosted production examples.
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

- `docker-compose.yml`
- `.env.example`
- Backup script
- Restore script
- Upgrade documentation
- Helm chart after Docker Compose path is stable
