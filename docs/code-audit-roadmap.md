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
| P0 | Add authentication and household-level authorization | completed |
| P1 | Decompose frontend server state and remove full-dashboard reloads | completed |
| P1 | Refactor projections around pure, typed inputs and policies | not started |
| P1 | Separate development deployment from supported production deployment | not started |
| P2 | Extract focused component boundaries from large frontend pages | in progress |
| P2 | Bring documentation, licensing, and CI in line with the implementation | not started |

## P0: Authentication and household authorization

**Status:** `completed`

Authentication, household authorization, import-root confinement, and secure development defaults are implemented: Argon2 password hashing, revocable database-backed cookie sessions, initial-owner setup, login/logout/status endpoints, authentication gates, household-scoped resource checks, and owner/admin/member/viewer role enforcement. FinTrack imports require an explicit read-only root and reject paths or symlinks that escape it. Administrative tools are opt-in, and committed development ports bind to localhost.

### Original audit findings

- **Addressed:** application API routers require an authenticated user.
- **Addressed:** household and nested-resource access is checked against the authenticated user's membership; non-members receive a non-disclosing 404.
- **Addressed:** owner/admin/member/viewer roles enforce administrative, write, and read-only boundaries.
- **Partially addressed:** initial setup honors `single_household_mode`, and public signup is enforced; a full invitation workflow is not implemented.
- **Addressed:** the default Compose development configuration binds published ports to localhost and keeps admin tools disabled.
- **Addressed:** FinTrack import requires an authenticated owner/admin, the global feature flag, and a configured import root; traversal and symlink escapes are rejected.
- `docs/technical-design.md` identifies household authorization, password hashing, and session revocation as security requirements; these are now implemented.

### Intended work

1. [x] Choose and document the local authentication/session design.
2. [x] Add a `get_current_user` dependency.
3. [x] Centralize household membership and role authorization.
4. [x] Apply authorization to every household-scoped API, including exports and imports.
5. [x] Define and enforce permissions for owner, admin, member, and viewer roles.
6. [x] Enforce `public_signup` and initial `single_household_mode` setup behavior.
7. [x] Require owner/admin access for administrative tools.
8. [x] Restrict FinTrack imports to a configured import root and reject resolved paths outside it.
9. [x] Disable admin tools by default in normal Compose startup; use an explicit development override when needed.
10. [x] Add negative cross-household and cross-role tests.

### Completion criteria

- Unauthenticated requests cannot read or mutate financial data.
- A member of one household cannot access another household by guessing or supplying its UUID.
- Viewer/member/admin/owner boundaries are covered by API tests.
- Signup and single-household settings have documented, tested behavior.
- Import paths cannot escape the configured import root.
- Administrative operations require both configuration enablement and an authorized principal.

### Deployment note

The P0 local/trusted-network security milestone is complete. Production deployment hardening—including a production frontend server, HTTPS termination, generated credentials, and internal-only service networking—remains tracked separately under the P1 deployment item.

## P1: Frontend data and state architecture

**Status:** `completed`

### Directly verified findings

- `frontend/src/App.tsx` is now 411 lines and primarily owns routing, workspace selection, theme handling, shared financial queries, and projection execution.
- `frontend/src/pages/PlanningPage.tsx` is over 1,700 lines after absorbing all route-owned planning workflows, so its internal domain boundaries now need extraction in the separate frontend component-boundaries item.
- The original baseline loaded 18 API collections centrally and requested account events separately for every account. The first implemented slice batches household events and moves accounts, events, snapshots, and financial-summary data into TanStack Query.
- Snapshot filtering and historical interpolation originally triggered the same full refresh. They now issue one domain-specific request each.
- Household membership is shared query state because authorization applies throughout the workspace; membership mutations, user administration, capabilities, imports, and exports are owned by `HouseholdSettingsPage`.
- The central `refreshDashboard()` path has been eliminated.
- Reproducible before/after counts are recorded in [`frontend-request-performance.md`](frontend-request-performance.md).

The measured performance impact and regression budgets are recorded in the linked request-performance document.

### Intended work

1. Separate server state from local form/draft state.
2. Introduce domain-specific query hooks, using a query cache such as TanStack Query or a small equivalent abstraction.
3. Load data by active route/domain rather than loading the whole household workspace up front.
4. Invalidate only affected query keys after mutations.
5. Add a household-level account-events endpoint or another batched retrieval mechanism to remove the per-account request pattern.
6. Extract page/domain mutation handlers from `App()`.
7. Preserve stale-request protection or replace it with query cancellation that provides equivalent behavior.

Suggested initial slices:

- Snapshots and snapshot filtering — route-owned query state and mutations implemented
- Accounts and account events — query reads, event batching, local drafts, and route-owned mutations implemented
- Real estate — properties, analytics, mortgages, sales, liquidation strategies, and related mutations are route-owned
- Planning data — account events, real estate, budget data, income sources, people, Social Security, transfers, and settings are route-owned
- Household membership/settings — shared membership query and route-owned settings mutations implemented

### Implementation progress

- [x] Record automated request-count baselines and before/after measurements.
- [x] Add TanStack Query with cancellation-aware domain query hooks.
- [x] Add a household-level account-events endpoint to remove per-account event requests.
- [x] Move accounts, events, snapshots, and financial summaries out of component-owned server state.
- [x] Limit snapshot filters, interpolation toggles, and snapshot mutations to affected query keys.
- [x] Extract snapshot queries, local state, and mutation handlers from `App()` into the Update route.
- [x] Extract account create/edit state and mutation handlers from `App()` into the Assets route.
- [x] Extract account-event query state, drafts, and mutation handlers from `App()` into the Planning route.
- [x] Extract property, property-analytics, and mortgage queries and mutations into the Assets route.
- [x] Extract real-estate sales and liquidation strategies into the Planning route.
- [x] Extract spending-item and annual-tax-record queries and mutations into the Planning route.
- [x] Extract income-source, household-person, and Social Security queries and mutations into the Planning route.
- [x] Extract projection-transfer and projection-settings queries and mutations into the Planning route.
- [x] Migrate remaining route domains and eliminate the central dashboard refresh.

### Completion criteria

- Changing a snapshot filter fetches only snapshot-related data.
- Account events are not fetched with one request per account.
- A mutation refreshes or updates only affected data.
- Page-specific data is fetched only when needed.
- `App()` is primarily routing, workspace selection, theme handling, and top-level error boundaries.
- Request counts for initial load and representative mutations are recorded before and after the change.

## P2: Frontend component boundaries

**Status:** `completed`

### Directly verified findings

- `frontend/src/pages/PlanningPage.tsx` fell from 1,765 to 123 lines after all major Planning domains were extracted.
- Extracted sections own their local edit state and mutations while consuming shared cached data needed by projection orchestration.
- `PlanningPage` now composes domain sections and retains only shared query data and route-level projection callbacks.

### Intended work

1. Extract route sections with their local state and mutations rather than creating presentation-only wrappers.
2. Keep query ownership at the narrowest component that needs the data, while allowing shared query observers where two sections genuinely consume the same cache entry.
3. Preserve request-count budgets and user-visible loading and error behavior.
4. Prefer domain components such as projection events, budget, Social Security, and real-estate planning over generic layout abstractions.

### Implementation progress

- [x] Extract projection-event state, queries, mutations, and responsive rendering.
- [x] Extract spending-plan state, mutations, errors, and rendering.
- [x] Extract household-person and Social Security state, mutations, errors, and rendering.
- [x] Extract automatic and planned real-estate sale mutations, errors, and rendering.
- [x] Extract income-source and annual-tax-record mutations, errors, and rendering.
- [x] Extract projection settings, spending coordination, transfers, and result rendering.
- [x] Reduce `PlanningPage` to route-level orchestration and genuinely shared projection state.

### Completion criteria

- `PlanningPage` primarily composes domain sections and coordinates only shared projection concerns.
- Extracted sections own their domain-local state, query observers, mutations, errors, and pending UI.
- Existing desktop, mobile, accessibility, navigation, and request-count tests continue to pass.

## P1: Projection engine boundaries

**Status:** `in progress`

### Directly verified findings

- `backend/app/analytics/projections.py` is 2,008 lines after persistence loading and the database-free entry point were separated.
- The route-facing `calculate_net_worth_projection()` adapter spans 30 lines; the in-memory `calculate_projection_from_input()` core spans 611 lines.
- The compatibility adapter accepts a SQLAlchemy `Session`, while the deterministic core consumes a detached `ProjectionInput`, resolves settings, executes projection behavior, performs optimization, and formats the response.
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

### Implementation progress

- [x] Extract projection-specific SQLAlchemy queries into `load_projection_input()`.
- [x] Add an immutable transitional `ProjectionInput` container and parity coverage.
- [ ] Convert ORM-backed input members to immutable plain-data records.
- [x] Make deterministic projection calculation operate without a database session.
- [ ] Extract focused projection policies and response formatting.

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
| 2026-07-25 | Database-free projection core | Split the route-facing persistence adapter from `calculate_projection_from_input()`, moved optimization candidate runs onto the in-memory core, and verified output parity with a detached input. |
| 2026-07-25 | Projection input-loading boundary | Extracted projection persistence queries and cost-basis resolution into `projection_input.py`, added an immutable transitional input contract, and verified injected-input output parity. |
| 2026-07-25 | Planning boundary completion | Extracted projection settings, spending coordination, recurring transfers, and projection results into focused components; `PlanningPage` fell from 686 to 123 lines and the frontend component-boundary audit item was completed. |
| 2026-07-25 | Planning income and tax boundary | Extracted income-source and annual-tax-record mutations, errors, and rendering into `IncomeAndTaxSection`; `PlanningPage` fell from 845 to 686 lines. |
| 2026-07-25 | Planning real-estate boundary | Extracted automatic and planned property-sale mutations, errors, and rendering into real-estate planning sections; `PlanningPage` fell from 1,030 to 845 lines. |
| 2026-07-25 | Planning Social Security boundary | Extracted household-person and Social Security estimate state, mutations, errors, and rendering into `SocialSecuritySection`; `PlanningPage` fell from 1,268 to 1,030 lines. |
| 2026-07-25 | Planning spending boundary | Extracted spending-item state, mutations, errors, and rendering into `SpendingPlanSection`; `PlanningPage` fell from 1,441 to 1,268 lines. |
| 2026-07-25 | Planning component boundaries | Extracted projection-event state, queries, mutations, and responsive UI into `PlanningEventsSection`; `PlanningPage` fell from 1,765 to 1,441 lines. |
| 2026-07-22 | Household settings data | Moved users, capabilities, membership mutations, imports, and exports into Settings; removed `refreshDashboard()` and reduced initial requests from 18 to 14. |
| 2026-07-22 | Planning projection configuration | Moved projection transfers and settings into Planning; initial Overview requests fell from 22 to 18. |
| 2026-07-22 | Planning people data | Moved income sources, household people, and Social Security estimates into Planning; initial Overview requests fell from 28 to 22. |
| 2026-07-22 | Planning budget data | Moved spending items and annual tax records into Planning; initial Overview requests fell from 32 to 28. |
| 2026-07-22 | Planning real estate | Moved planned sales and liquidation strategies into Planning; initial Overview requests fell from 36 to 32. |
| 2026-07-22 | Asset real estate | Moved properties, property analytics, mortgages, and related mutations into Assets; initial Overview requests fell from 42 to 36. |
| 2026-07-22 | Account events | Moved account-event loading, drafts, and mutations into Planning; Overview no longer requests account events. |
| 2026-07-22 | Account mutations | Moved account create/edit state and mutations into Assets with targeted account and financial-summary invalidation. |
| 2026-07-22 | Snapshot domain | Moved snapshot loading, filters, drafts, and mutations into the Update route; Overview no longer requests snapshots. |
| 2026-07-22 | Frontend server state | Added request-count baselines, household event batching, and the first TanStack Query slice for accounts, snapshots, events, and financial summaries. |
| 2026-07-22 | P0 security | Confined imports to an explicit root, made admin tools opt-in, bound development ports to localhost, and marked the security milestone complete. |
| 2026-07-22 | Household authorization | Added household/resource isolation, role enforcement, protected membership administration, and cross-household tests. |
| 2026-07-22 | Authentication | Started local password authentication and revocable cookie-session implementation. |
| 2026-07-22 | Audit roadmap | Initial audit findings accepted and documented. |
