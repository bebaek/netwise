# Technical Design

## Architecture overview

Netwise should be a modular web application with a Python backend, relational database, background workers, and a browser-based frontend.

Primary components:

- Web frontend
- API backend
- PostgreSQL database
- Background worker
- Optional Redis queue/cache
- Optional plugin runner

## Backend

Recommended stack:

- FastAPI for HTTP APIs
- Pydantic for request and response schemas
- SQLAlchemy for ORM
- Alembic for migrations
- PostgreSQL for persistence
- pytest for tests

Suggested package layout:

```text
backend/
  app/
    main.py
    api/
      routes/
    core/
      config.py
      security.py
    db/
      models.py
      session.py
    schemas/
    services/
    analytics/
      projection_engine.py
      time_series.py
      yield_models.py
      mortgage.py
      expense_estimation.py
    workers/
    tests/
```

## Frontend

Recommended stack:

- React or Next.js
- TypeScript
- Component library selected later
- Charting library selected later

Major screens:

- Household dashboard
- Account list
- Account detail and balance history
- Balance snapshot entry
- Guided update workflow
- Income sources
- Annual tax summaries
- Projection scenarios
- Projection results
- Settings and members

## Multi-user and tenancy model

Financial data should belong to a household/workspace rather than directly to a single user.

Core entities:

```text
User
Household
HouseholdMembership
Account
BalanceSnapshot
AccountEvent
RealEstateProperty
MortgageProfile
IncomeSource
AnnualTaxRecord
ProjectionScenario
ProjectionResult
InstitutionGuide
```

Roles:

- Owner
- Admin
- Editor
- Viewer

Most domain tables should include `household_id`.

## Data model sketch

### Household

```text
id
name
created_at
updated_at
```

### HouseholdMembership

```text
id
household_id
user_id
role
created_at
```

### Account

```text
id
household_id
name
institution_name
account_kind
category
liquidity_class
currency
is_active
created_at
updated_at
```

### BalanceSnapshot

```text
id
household_id
account_id
as_of_date
balance
currency
source
confidence_level
metadata_json
created_by_user_id
created_at
```

Recommended constraints:

- Unique account snapshot per account and date.
- Balance stored as decimal/numeric.
- Liability balances stored as positive values and subtracted according to `account_kind`.
- Index by household/date and account/date.

For real estate asset accounts, snapshots represent property valuation snapshots. `source`, `confidence_level`, and `metadata_json` should capture whether the value came from manual estimate, appraisal, purchase price, tax assessment, comparable sales, plugin estimate, or model estimate.

### AccountEvent

Account events are dated changes or explanatory adjustments separate from balance snapshots.

```text
id
household_id
account_id
event_date
amount
currency
event_type
description
projection_behavior
scenario_id
created_by_user_id
created_at
updated_at
```

`projection_behavior` controls whether the event is historical-only, projection-only, or both. `scenario_id` is nullable for baseline events and set for scenario-specific events.

### AnnualTaxRecord

```text
id
household_id
tax_year
gross_income
total_taxes_paid
refund_or_amount_due
notes
created_at
updated_at
```

### ProjectionScenario

```text
id
household_id
name
start_date
end_date
inflation_rate
default_expense_growth_rate
assumptions_json
created_at
updated_at
```

## Analytics layer

Projection and financial math should live in pure Python modules separate from API routes.

Initial modules:

- `projection_engine.py`
- `mortgage.py`
- `yield_models.py`
- `expense_estimation.py`
- `time_series.py`

This keeps formulas testable and reusable.

## Projection engine

Initial projection should be deterministic.

Inputs:

- Latest balances
- Historical snapshots
- Account categories
- Account-level yield assumptions
- Category-level yield defaults
- Real estate valuation snapshots
- Real estate assumptions
- Mortgage assumptions
- Income sources
- Annual tax summaries
- Expense assumptions
- Account events and adjustments

Outputs:

- Time-indexed net worth
- Liquid asset projection
- Retirement asset projection
- Real estate equity projection
- Liability projection
- Estimated expense projection

## Financial precision

Stored monetary values should use database numeric/decimal types.

Application-level financial values should use Python `Decimal` for persistence-facing code. Analytics may convert to floats when appropriate for statistical calculations, but persisted values should remain decimal.

## Authentication

Initial implementation can support local account authentication.

Design should allow additional identity providers later through a separate identity table:

```text
UserIdentity
  user_id
  provider
  provider_subject
```

Security requirements:

- Strong password hashing
- Optional two-factor authentication later
- Session revocation
- Household-level authorization checks
- Audit log for sensitive changes later

## Plugins

Plugins are optional future functionality.

Plugin principles:

- Disabled by default.
- Isolated from the main API process.
- Permissioned by capability.
- Never store credentials in guide definitions.
- Browser automation runs only in a dedicated runner.

Plugin types:

- API-based balance extraction
- Browser automation balance extraction
- Importer/exporter plugins

## Data portability

The app should support:

- CSV export
- JSON export
- Full household export
- Import from full household export

## Testing strategy

Highest-priority tests:

- Projection formulas
- Mortgage amortization
- Expense estimation
- Authorization boundaries
- Snapshot uniqueness and ordering
- Decimal handling
- Import/export round trips

## Development phases

### Phase 1

- Account CRUD
- Snapshot CRUD
- Household and membership model
- Basic dashboard
- Income and tax records
- Deterministic projection engine

### Phase 2

- Guided manual update workflows
- Real estate and mortgage modeling
- Scenario comparison
- CSV/JSON export

### Phase 3

- Background jobs
- Advanced charting
- Yield strategies
- Import support

### Phase 4

- Optional plugins
- Time-series forecasting
- Monte Carlo simulations
- Advanced permissions and audit logs
