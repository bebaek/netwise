# Code Audit Improvement Roadmap

## Status

**Accepted for future tracking.**

- Audit date: 2026-07-22
- Audited revision: `7fa9100`
- Default owner: unassigned
- Review cadence: update this document when an item is started, completed, superseded, or split into an issue/ADR

Status values used below:

- `not started`
- `in progress`
- `blocked`
- `completed`
- `superseded`

## Baseline validation

The following checks passed at the audited revision:

- Backend: `uv run --extra dev pytest -q` — 56 tests passed
- Backend: `uv run --extra dev ruff check .` — passed
- Frontend: `npm run lint` — passed
- Frontend: `npm run build` — passed
- Git working tree was clean

Playwright was not run because its configured workflow requires the live Docker Compose application and a seeded database. Backend tests emitted one FastAPI/Starlette test-client deprecation warning.

## Priority summary

| Priority | Improvement | Status |
| --- | --- | --- |
| P0 | Add authentication and household-level authorization | not started |
| P1 | Decompose frontend server state and remove full-dashboard reloads | not started |
| P1 | Refactor projections around pure, typed inputs and policies | not started |
| P1 | Separate development deployment from supported production deployment | not started |
| P2 | Bring documentation, licensing, and CI in line with the implementation | not started |

## P0: Authentication and household authorization

**Status:** `not started`

### Directly verified findings

- API routes do not have an authenticated-user dependency. User records can be listed and created through `backend/app/api/routes/users.py`.
- Household access is based on caller-supplied identifiers. `list_households` returns every household when `user_id` is omitted.
- Membership roles are validated, but route authorization does not enforce owner/editor/viewer permissions.
- `public_signup` and `single_household_mode` are defined in `backend/app/core/config.py` but are not used by application behavior.
- The default Compose development configuration publishes the backend and enables admin tools.
- The FinTrack import API accepts a caller-provided directory, resolves it on the backend host/container, and is protected only by the global admin-tools feature flag.
- `docs/technical-design.md` already identifies household authorization, password hashing, and session revocation as security requirements.

### Intended work

1. Choose and document the local authentication/session design.
2. Add a `get_current_user` dependency.
3. Centralize authorization dependencies such as:
   - `require_household_member`
   - `require_household_editor`
   - `require_household_owner`
4. Apply authorization to every household-scoped API, including exports and imports.
5. Define and enforce permissions for owner, editor, and viewer roles.
6. Make `public_signup` and `single_household_mode` effective, or remove them until implemented.
7. Require owner/admin access for administrative tools.
8. Restrict FinTrack imports to a configured import root and reject resolved paths outside it.
9. Disable admin tools by default in normal Compose startup; use an explicit development profile or override when needed.
10. Add negative cross-household and cross-role tests.

### Completion criteria

- Unauthenticated requests cannot read or mutate financial data.
- A member of one household cannot access another household by guessing or supplying its UUID.
- Viewer/editor/owner boundaries are covered by API tests.
- Signup and single-household settings have documented, tested behavior.
- Import paths cannot escape the configured import root.
- Administrative operations require both configuration enablement and an authorized principal.

### Interim safety requirement

Until this item is complete, documentation should call the application local/trusted-network only. Published ports should bind to localhost where practical, and the application should not be represented as safe for an untrusted multi-user network.

## P1: Frontend data and state architecture

**Status:** `not started`

### Directly verified findings

- `frontend/src/App.tsx` is 1,486 lines, and `App()` owns most server data, form drafts, mutations, loading state, and error state.
- `refreshDashboard()` begins 18 API requests and then requests account events separately for every account.
- The same full refresh runs when only the snapshot filter or historical interpolation option changes.
- Approximately 28 mutation paths call `refreshDashboard()`, causing small changes to reload unrelated domains.
- Data for all pages is loaded centrally even though page modules are lazy-loaded.

The expected performance and maintainability impact is an inference from this directly verified request pattern; it should be measured during implementation.

### Intended work

1. Separate server state from local form/draft state.
2. Introduce domain-specific query hooks, using a query cache such as TanStack Query or a small equivalent abstraction.
3. Load data by active route/domain rather than loading the whole household workspace up front.
4. Invalidate only affected query keys after mutations.
5. Add a household-level account-events endpoint or another batched retrieval mechanism to remove the per-account request pattern.
6. Extract page/domain mutation handlers from `App()`.
7. Preserve stale-request protection or replace it with query cancellation that provides equivalent behavior.

Suggested initial slices:

- Snapshots and snapshot filtering
- Accounts and account events
- Real estate
- Planning data
- Household membership/settings

### Completion criteria

- Changing a snapshot filter fetches only snapshot-related data.
- Account events are not fetched with one request per account.
- A mutation refreshes or updates only affected data.
- Page-specific data is fetched only when needed.
- `App()` is primarily routing, workspace selection, theme handling, and top-level error boundaries.
- Request counts for initial load and representative mutations are recorded before and after the change.

## P1: Projection engine boundaries

**Status:** `not started`

### Directly verified findings

- `backend/app/analytics/projections.py` is 2,149 lines.
- `calculate_net_worth_projection()` spans roughly 710 lines.
- The function accepts a SQLAlchemy `Session`, loads ORM data, resolves settings, executes projection behavior, performs optimization, and formats the response.
- `docs/projection-strategy-architecture.md` already proposes separating input loading, strategies, policies, and presentation.

### Intended work

Refactor incrementally while retaining the current deterministic output:

1. Add immutable, plain-data contracts such as:
   - `ProjectionInput`
   - `ProjectionAssumptions`
   - `ProjectionResult`
2. Extract `load_projection_input(db, household_id, ...)` as the persistence boundary.
3. Make deterministic projection calculation operate without a database session or ORM models.
4. Extract cohesive policies, starting with:
   - withdrawal order and liquidation costs
   - spending
   - income timing
   - tax treatment
   - property sales
5. Include strategy key/version and resolved assumptions in results where needed for reproducibility.
6. Use existing tests as characterization tests and add focused unit tests for extracted policies.

### Completion criteria

- The core deterministic engine can run from plain in-memory inputs.
- SQLAlchemy access is isolated to an input-loading layer.
- API response formatting is not part of core simulation logic.
- Existing projection behavior remains covered and unchanged unless a change is explicitly documented.
- Policy decisions can be tested independently.
- The architecture document is updated from `Proposed` to reflect implemented boundaries.

## P1: Development and production deployment separation

**Status:** `not started`

### Directly verified findings

- The frontend container runs Vite's development server rather than a production static build.
- PostgreSQL, backend, and frontend ports are published by the default Compose configuration.
- Development database credentials are hardcoded.
- Admin tools are enabled in the default Compose configuration.
- Backend startup runs Alembic automatically before Uvicorn.
- The backend Docker build does not use `uv.lock`; the frontend build uses `npm install` rather than `npm ci`.
- `docs/self-hosted-operations.md` lists configuration variables that are not implemented and uses `DATABASE_URL` where current settings require `NETWISE_DATABASE_URL`.
- The operations document calls health endpoints planned even though they are implemented.
- The README's `.env` copy step does not configure the hardcoded Compose service values.

### Intended work

Create clearly distinct deployment modes.

Development mode may retain:

- Vite development server
- Published database/backend ports
- Demo data and optional admin tools
- Fast rebuild/reload behavior

Production mode should provide:

- A multi-stage frontend build served by a production static server or reverse proxy
- HTTPS termination guidance
- Internal-only backend and database networking
- Generated credentials and secrets supplied outside tracked files
- Admin tools disabled by default
- An explicit, one-shot migration command/job
- Reproducible dependency installation using lockfiles
- Container health checks
- Tested backup, restore, and upgrade procedures

### Completion criteria

- Development and production commands are unambiguous.
- Production startup does not use the Vite development server.
- Only the intended HTTP/HTTPS entry point is publicly exposed by the production example.
- Production configuration has no committed default database password.
- Migrations have a documented, safe execution path.
- Docker builds use `uv.lock` and `npm ci`, or document an equivalent reproducible mechanism.
- Backup and restore instructions have been exercised against the production Compose path.

## P2: Documentation, licensing, and CI

**Status:** `not started`

### Intended work

1. Add an implementation status table to the README with `implemented`, `experimental`, and `planned` capabilities.
2. Replace machine-specific paths such as `/Users/burm/code/netwise` with repository-relative commands.
3. Update planned-stack wording now that the backend and frontend stacks are implemented.
4. Make operations documentation match actual setting names and supported behavior.
5. Choose a license before describing the repository as open source.
6. Add continuous integration for:
   - Ruff
   - backend tests
   - frontend type checking and build
   - migration from an empty database
   - at least a desktop Playwright smoke test
7. Resolve the FastAPI/Starlette test-client deprecation warning when the supported dependency path is clear.

### Completion criteria

- A new contributor can distinguish current capability from roadmap intent.
- Quickstart commands are portable across checkout locations.
- Every documented environment variable maps to implemented configuration.
- The repository contains a selected license.
- Pull requests automatically run the core validation suite.

## Suggested implementation order

1. Clarify local-only safety language and disable default admin tools.
2. Implement authentication and household authorization.
3. Restrict administrative import paths.
4. Split the frontend snapshot/account-event data flow as the first frontend architecture slice.
5. Extract projection input loading, then one policy at a time.
6. Add the production Compose path and reconcile operations documentation.
7. Add CI, licensing, and remaining documentation cleanup.

## Tracking notes

When an item moves to a dedicated issue or ADR, add its link here rather than duplicating detailed implementation discussion. Keep the completion criteria in this document synchronized with any resulting plan.

| Date | Item | Update |
| --- | --- | --- |
| 2026-07-22 | Audit roadmap | Initial audit findings accepted and documented. |
