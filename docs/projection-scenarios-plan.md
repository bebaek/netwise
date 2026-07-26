# Projection Scenarios Implementation Plan

## Status

**In progress.**

- [x] Slice 1: scenario identity, baseline migration, CRUD, and authorization
- [x] Slice 2: scenario-aware persisted projection inputs
- [x] Slice 3: transactional duplication and data portability
- [ ] Slice 4: frontend scenario editing
- [ ] Slice 5: scenario comparison
- [ ] Slice 6: compatibility cleanup

- Plan date: 2026-07-25
- Initial milestone: named, independently editable deterministic scenarios with comparison
- Intended delivery: incremental migrations and reviewable vertical slices

## Objective

Projection scenarios should let a household preserve a baseline plan, create independent alternatives, and compare outcomes without modifying historical financial records or current account balances.

Representative questions include:

- What if retirement starts earlier or later?
- What if investment returns are lower?
- What if income ends sooner?
- What if spending changes in retirement?
- What if a property is sold on a different date?
- What if Social Security is claimed at a different age?

The existing deterministic projection engine remains the calculation authority. Scenario work should change how persisted projection inputs are selected, not duplicate the calculation engine.

## Current architecture

The implementation already provides useful boundaries for this work:

- `load_projection_input` resolves SQLAlchemy records into an immutable `ProjectionInput`.
- `calculate_projection_from_input` executes the deterministic calculation without retaining ORM entities.
- Projection settings, income, spending, transfers, planned property sales, liquidation strategies, and future account events are persisted separately.
- `AccountEvent.scenario_id` exists but is not currently a foreign key or used by the input loader.
- TanStack Query isolates planning query keys and mutations from the page components.
- Projection results are calculated on demand and are not persisted.

Current persisted planning records are household-wide. `ProjectionSettings` is uniquely constrained by `household_id`, and the projection input loader selects all planning records for the household. Scenario support must replace those implicit household-wide selections with explicit scenario selection.

## Product decisions

### Materialized scenarios, not inheritance

A duplicated scenario is an independent snapshot of the source scenario's planning assumptions at the time of duplication.

Subsequent edits do not flow between scenarios. This avoids hidden inheritance rules and makes a saved scenario reproducible. The UI must explain that duplication creates an independent copy.

### Shared facts versus scenario-owned assumptions

The following records describe household facts and remain shared:

- Household and membership
- Household people
- Accounts and account categories
- Balance snapshots and current balances
- Real-estate property identity
- Mortgage contract identity
- Historical account events
- Annual tax records

The following records affect future assumptions and become scenario-owned:

- Projection settings
- Spending items
- Income sources
- Social Security estimates and their generated income sources
- Projection transfers
- Planned real-estate sales
- Automatic real-estate liquidation strategies
- Projection-only account events
- Account yield and liquidation-cost assumptions
- Property appreciation and rental-growth assumptions

Historical records remain unchanged when a scenario is edited or deleted.

### Baseline scenario

Every household has exactly one baseline scenario.

- Existing households receive a `Baseline` scenario during migration.
- New households receive a baseline scenario when the household is created.
- Existing planning assumptions migrate into the baseline.
- The baseline can be renamed but cannot be deleted.
- Other scenarios may be duplicated or deleted.
- The API resolves a missing `scenario_id` to the baseline during a compatibility period.

### No persisted projection runs in the first milestone

Projection results continue to be calculated on demand. Persisted result snapshots, background calculations, probabilistic runs, and result history are separate future work.

## Data model

### `ProjectionScenario`

Add a `projection_scenarios` table:

```text
id                       UUID primary key
household_id             UUID foreign key -> households.id
name                     varchar(120)
description              varchar(1000), nullable
is_baseline              boolean, default false
created_from_scenario_id UUID foreign key -> projection_scenarios.id, nullable
created_at               timestamp with time zone
updated_at               timestamp with time zone
```

Constraints and indexes:

- Unique `(household_id, name)`.
- At most one baseline per household, enforced with PostgreSQL and SQLite partial unique indexes.
- Index `(household_id, created_at)` for ordered listing.
- Application validation strips names and limits a household to 20 scenarios initially.

All scenario lookup helpers must validate that the scenario belongs to the requested household before reading or changing assumptions.

### Existing scenario-owned tables

Add `scenario_id` foreign keys and indexes to:

- `projection_settings`
- `spending_items`
- `income_sources`
- `social_security_estimates`
- `projection_transfers`
- `real_estate_sales`
- `real_estate_liquidation_strategies`

Replace constraints as follows:

- Projection settings: unique `scenario_id` instead of unique `household_id`.
- Social Security estimates: unique `(scenario_id, person_id)` instead of unique `person_id`.
- Planned property sales: unique `(scenario_id, property_account_id)`.
- Liquidation strategies: unique `(scenario_id, property_account_id)`.

Retain `household_id` on these tables for authorization, defensive consistency checks, and efficient household cleanup. Creation and update services must enforce `record.household_id == scenario.household_id`.

### Account events

Convert the existing nullable `account_events.scenario_id` column into a foreign key to `projection_scenarios.id`.

Rules:

- `historical_only` events have `scenario_id = NULL` and never enter projections.
- Shared `historical_and_projection` events have `scenario_id = NULL` and apply to every scenario.
- `projection_only` events must have a scenario.
- Scenario-specific historical events are deliberately unsupported because one record must not describe different household history depending on the selected future.

Enforce these combinations in validation and, where portable, a database check constraint. The loader includes shared `historical_and_projection` events plus `projection_only` events belonging to the selected scenario.

### Scenario account assumptions

Add `projection_scenario_account_assumptions`:

```text
id                       UUID primary key
scenario_id              UUID foreign key -> projection_scenarios.id
household_id             UUID foreign key -> households.id
account_id               UUID foreign key -> accounts.id
expected_annual_yield    numeric(8, 6), nullable
liquidation_expense_rate numeric(8, 6), nullable
created_at               timestamp with time zone
updated_at               timestamp with time zone
```

Use unique `(scenario_id, account_id)`.

The baseline migration materializes effective values from each account. Scenario duplication copies these rows. This prevents later edits in one scenario from changing another scenario implicitly. Creating a new shared account initializes an assumption row in every existing scenario; deleting an account cascades its scenario assumptions.

### Scenario property assumptions

Add `projection_scenario_property_assumptions`:

```text
id                         UUID primary key
scenario_id                UUID foreign key -> projection_scenarios.id
household_id               UUID foreign key -> households.id
property_account_id        UUID foreign key -> accounts.id
expected_appreciation_rate numeric(8, 6), nullable
rent_growth_rate           numeric(8, 6), nullable
vacancy_rate               numeric(8, 6), nullable
created_at                 timestamp with time zone
updated_at                 timestamp with time zone
```

Use unique `(scenario_id, property_account_id)`.

Other physical property and mortgage fields remain shared in the first milestone. More scenario-specific property operating assumptions can be added when a concrete comparison requires them. Creating a property initializes its planning-assumption row in every scenario; deleting the property account cascades those rows.

### Delete behavior

Scenario-owned records should use database cascades from `ProjectionScenario`. Shared accounts, people, properties, and historical records must not cascade when a scenario is deleted.

The service rejects deletion of the baseline. Scenario deletion is confirmation-gated in the UI.

## Migration strategy

Implement the schema transition in an Alembic migration that remains valid for both PostgreSQL production and SQLite tests.

1. Create `projection_scenarios` and assumption tables.
2. Create one baseline scenario for every existing household.
3. Add nullable `scenario_id` columns to scenario-owned tables.
4. Populate each existing planning record with its household's baseline scenario.
5. Materialize baseline account and property assumptions from current account/property fields.
6. Add foreign keys and scenario-aware unique constraints.
7. Make `scenario_id` non-null on records that are always scenario-owned.
8. Attach existing `projection_only` account events to the baseline; retain null on historical events.
9. Update household creation and owner-bootstrap paths to guarantee a baseline.

Before and after migration, run an equivalence test that projects a populated household with the same date range and verifies identical deterministic output.

A downgrade can retain only baseline data when returning to the household-wide schema. Because additional scenarios cannot be represented by the old schema, the downgrade must either fail when non-baseline scenarios exist or require their removal explicitly; it must not silently merge conflicting assumptions.

## Backend services

### Scenario service

Create a focused service module rather than putting clone logic in route handlers. Responsibilities:

- `get_baseline_scenario`
- `get_household_scenario`
- `create_baseline_scenario`
- `create_scenario`
- `duplicate_scenario`
- `rename_scenario`
- `delete_scenario`

`duplicate_scenario` runs in one transaction and copies:

- Projection settings
- Spending items
- Income sources
- Social Security estimates, remapping cloned income-source IDs
- Projection transfers
- Planned property sales
- Liquidation strategies
- Scenario-bound future account events
- Account assumptions
- Property assumptions

References to shared account, person, property, and household IDs remain unchanged.

### Projection input loader

Change the signature to:

```python
load_projection_input(
    db,
    household_id,
    scenario_id,
    *,
    start_date,
    end_date,
) -> ProjectionInput
```

The loader must:

- Validate household/scenario ownership once.
- Select scenario-owned records by `scenario_id`.
- Include shared projection-capable account events plus scenario-specific events.
- Apply scenario account/property assumptions while converting ORM records into immutable projection contracts.
- Continue using shared current balances, mortgages, annual tax records, and cost bases.

Add `scenario_id` and `scenario_name` to `ProjectionInput` and projection responses so results remain attributable after concurrent UI activity.

### Projection execution

`calculate_projection_from_input` remains scenario-agnostic. It receives a fully resolved immutable input exactly as it does now.

`calculate_net_worth_projection` becomes the compatibility adapter that resolves a missing scenario to the baseline and passes the selected ID to the loader.

## API design

### Scenario CRUD

```text
GET    /households/{household_id}/projection-scenarios
POST   /households/{household_id}/projection-scenarios
GET    /projection-scenarios/{scenario_id}
PATCH  /projection-scenarios/{scenario_id}
POST   /projection-scenarios/{scenario_id}/duplicate
DELETE /projection-scenarios/{scenario_id}
```

Create payload:

```json
{
  "name": "Retire early",
  "description": "Retirement begins in 2032",
  "source_scenario_id": "optional-uuid"
}
```

If `source_scenario_id` is supplied, creation delegates to the duplicate service. The dedicated duplicate route exists for a clearer UI action.

### Scenario-aware planning APIs

During migration, add an explicit `scenario_id` query parameter to planning list endpoints and `scenario_id` to create payloads. Settings become:

```text
GET /projection-settings/{household_id}?scenario_id={scenario_id}
PUT /projection-settings/{household_id}?scenario_id={scenario_id}
```

Apply the same selection to income sources, Social Security estimates, spending items, projection transfers, property sales, liquidation strategies, and projection-capable account events.

For one compatibility release, an omitted scenario resolves to the household baseline. New frontend code always sends an explicit scenario ID.

### Scenario assumption APIs

Expose account and property assumptions through the selected scenario rather than continuing to edit planning rates on shared account/property records:

```text
GET /projection-scenarios/{scenario_id}/account-assumptions
PUT /projection-scenarios/{scenario_id}/account-assumptions/{account_id}
GET /projection-scenarios/{scenario_id}/property-assumptions
PUT /projection-scenarios/{scenario_id}/property-assumptions/{property_account_id}
```

The existing account and property APIs continue to own physical identity and current facts. Once the frontend migrates, yield, liquidation-cost, appreciation, and rental-growth controls move into the scenario-aware Planning interface.

### Projection endpoint

Extend the existing endpoint:

```text
GET /dashboard/{household_id}/projection?scenario_id={scenario_id}&start_year=...&end_year=...
```

Return `scenario_id` and `scenario_name` in `NetWorthProjectionRead`.

### Comparison endpoint

Use a POST request because the scenario set and future comparison options may outgrow a safe query string:

```text
POST /dashboard/{household_id}/projection-comparison
```

Request:

```json
{
  "scenario_ids": ["uuid-1", "uuid-2"],
  "start_year": 2026,
  "end_year": 2066,
  "interval": "annual"
}
```

Validation:

- Two to four unique scenarios.
- Every scenario belongs to the household.
- Existing projection year and interval validation still applies.
- Comparison uses the same start/end range for every scenario.

Response per scenario includes the existing projection plus summary fields:

- Ending net worth
- Lowest net worth
- Lowest liquid-asset total
- First retirement-account withdrawal date
- First unfunded date
- Cumulative projected income
- Cumulative projected taxes
- Cumulative projected spending

No scenario is labeled “best.” Netwise presents deterministic outcomes and warnings without making investment recommendations.

## Authorization

Every new route must use the existing authenticated household authorization model.

Specific negative tests are required for:

- Listing another household's scenarios.
- Supplying a scenario from another household to a projection or planning endpoint.
- Duplicating a scenario into another household.
- Mutating or deleting a scenario without editor-level permission.
- Reading comparison results containing an unauthorized scenario ID.

Error responses should not disclose scenario names from unauthorized households.

## Frontend design

### Scenario selection

Add a scenario toolbar at the top of Planning:

- Current scenario selector
- Baseline badge
- New scenario action
- Duplicate action
- Rename/edit-description action
- Delete action for non-baseline scenarios
- Compare action

Store the selected scenario in the Planning route query string:

```text
/planning?scenario={scenario_id}
```

On an absent or invalid ID, select the baseline and replace the URL. This preserves selection across reloads and makes a scenario linkable within the household.

### Query architecture

Add `scenarioId` to every scenario-owned TanStack Query key:

```text
[household, householdId, planning, scenarioId, projection-settings]
[household, householdId, planning, scenarioId, income-sources]
[household, householdId, planning, scenarioId, spending-items]
```

Household people, accounts, snapshots, annual tax records, and physical property/mortgage records remain household-scoped. Account yields, liquidation costs, property appreciation, and rental growth are loaded through scenario-owned assumption keys and edited in Planning rather than shared asset forms.

Mutation invalidation must target only the selected scenario unless shared household facts changed. Projection results are keyed by household, scenario, year range, interval, and one-run overrides.

### Editing behavior

- Switching scenarios clears stale mutation errors and displays loading placeholders rather than data from the previous scenario.
- Existing immediate-save forms write only to the selected scenario.
- Duplicating shows the copied scenario only after the transaction succeeds.
- Deletion requires the scenario name in a confirmation dialog and then returns to baseline.
- The UI labels copied scenarios as independent; it does not imply future synchronization.

### Comparison view

The first comparison view supports two to four scenarios and annual results:

- Summary cards for the server-computed metrics.
- One net-worth line per scenario.
- One liquid-assets line per scenario.
- Warning and first-unfunded indicators per scenario.
- Accessible table fallback containing annual values.
- Stable color and line-style mapping that does not rely on color alone.

Detailed single-scenario cash-flow and account tables remain in the existing results view.

## Import, export, and demo data

### Household export

Extend household JSON export to include:

- Scenario metadata
- Scenario-owned planning records
- Account and property assumption overrides
- Source-scenario provenance when available

The export should preserve stable IDs within the export document so relationships can be reconstructed later.

### FinTrack import

FinTrack import targets the household baseline. It must not create one scenario per import run or mutate non-baseline scenarios.

### Demo seed

Create a baseline scenario with current demo assumptions and one alternative, such as `Conservative returns`, so manual and browser tests exercise selection and comparison.

Seed reset remains idempotent.

## Testing strategy

### Migration tests

- Every existing household receives exactly one baseline.
- Existing planning records attach to the correct baseline.
- Existing projection output is unchanged after migration.
- Scenario-aware uniqueness constraints allow the same property/person in different scenarios.
- Projection-only account events attach to baseline while historical events remain shared.
- Empty-database migration succeeds on PostgreSQL in CI.

### Service tests

- New household baseline creation is idempotent.
- Duplicate creates a deep independent copy.
- Social Security estimates point to the cloned income sources.
- Shared account/property/person references are preserved.
- A failed copy rolls back all cloned rows.
- Baseline deletion is rejected.
- Cross-household references are rejected.

### Projection tests

- Selecting two scenarios with different settings produces independent deterministic results.
- Identical scenarios produce identical results.
- Scenario yield overrides affect only their selected scenario.
- Shared current balances and historical events are consistent across scenarios.
- Scenario-specific future events do not leak across scenarios.
- Comparison summaries equal values derived from their detailed points.

### API and authorization tests

- CRUD, duplicate, limits, validation, and baseline fallback.
- Owner/editor/viewer permissions.
- Cross-household denial for every ID-based operation.
- Comparison request limits and duplicate-ID rejection.
- Compatibility behavior when `scenario_id` is omitted.

### Frontend and Playwright tests

- Baseline is selected on first load.
- Selection survives reload and browser navigation.
- Duplicate, rename, and delete workflows.
- Editing one scenario leaves another unchanged.
- Comparison renders summaries, charts, and accessible table content.
- Mobile scenario controls remain usable.
- Representative API request counts do not regress through accidental duplicate loading.

## Delivery sequence

### Slice 1: Scenario identity and migration

**Status:** Complete.

- Add models and Alembic migration.
- Backfill baseline scenarios.
- Add baseline creation to household bootstrap.
- Add scenario CRUD schemas, service, routes, and authorization tests.

Completion signal: every household has a baseline and scenario CRUD is safe, while current projection behavior remains unchanged.

### Slice 2: Scenario-aware persisted inputs

**Status:** Complete.

- Add scenario ownership to planning entities.
- Add account/property assumption tables.
- Update loader and projection endpoint.
- Preserve baseline fallback compatibility.
- Add deterministic pre/post-migration equivalence tests.

Completion signal: two scenarios can produce isolated backend projections.

### Slice 3: Transactional duplication

**Status:** Complete.

- Deep-copy scenario-owned records.
- Remap Social Security income sources.
- Add rollback and cross-household tests.
- Update export, import, and seed behavior.

Completion signal: a complete scenario can be cloned and then edited independently.

### Slice 4: Frontend scenario editing

- Add selector and URL state.
- Make query keys, forms, and mutations scenario-aware.
- Add create, duplicate, rename, and delete controls.
- Add desktop and mobile Playwright coverage.

Completion signal: users can manage and edit scenarios without data leakage or stale UI state.

### Slice 5: Comparison

- Add comparison request/response schemas and endpoint.
- Compute summary metrics server-side.
- Add comparison cards, charts, warnings, and accessible table.
- Add deterministic API and Playwright tests.

Completion signal: users can compare two to four scenarios over the same time range.

### Slice 6: Compatibility cleanup

- Confirm all supported clients send explicit scenario IDs.
- Decide whether omitted IDs remain a permanent baseline convenience or become an API error.
- Reconcile documentation, API examples, and request-count budgets.

## Acceptance criteria

The milestone is complete when:

- Every household has exactly one usable baseline scenario.
- Existing installations preserve their prior baseline projection results after migration.
- Users can create, duplicate, rename, select, and delete non-baseline scenarios.
- Scenario-owned assumptions and future events never leak between scenarios.
- Current balances and historical records remain shared and unchanged.
- Two to four scenarios can be compared with attributable deterministic results.
- Household authorization protects all scenario APIs.
- Household export, FinTrack import, and demo seed behave intentionally with scenarios.
- Backend, migration, frontend, production-build, and desktop Playwright CI remain green.

## Explicit non-goals

- Monte Carlo or probabilistic projection
- Automatic recommendation of a preferred scenario
- Persisted projection result history
- Background projection workers
- Collaborative real-time scenario editing
- Cross-household scenario sharing
- Scenario inheritance or automatic synchronization
- Detailed tax-bracket optimization
- Mobile-native applications

## Risks and mitigations

### Migration breadth

Many planning tables become scenario-owned. Mitigate with a baseline backfill, deterministic equivalence tests, and small schema/service slices before UI changes.

### Clone consistency

A partial clone would be misleading. Keep duplication in one database transaction and test rollback after an injected failure.

### Ambiguous shared data

Clearly classify facts versus assumptions. New fields must document whether they are household-shared or scenario-owned before implementation.

### Query-cache leakage

Scenario ID must be part of every scenario-owned query key. Add a test that switches rapidly between scenarios and asserts that prior data is not rendered under the new name.

### Performance

Comparison executes up to four deterministic projections. Reuse resolved shared household facts where practical, cap scenario count and date range, and profile before introducing background jobs or caching.

### API transition

Baseline fallback protects existing clients while the frontend migrates. Log or test fallback use, then make a deliberate compatibility decision in Slice 6 rather than leaving accidental behavior.
