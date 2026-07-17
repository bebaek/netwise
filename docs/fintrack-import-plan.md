# Fintrack Data Import Plan

## Goal

Import an existing `fintrack` data directory into a Netwise household.

Expected `fintrack` files:

```text
{name}-condition.toml
{name}-values.csv
{name}-value-changes.csv
```

Target Netwise concepts:

```text
fintrack condition         -> Netwise account metadata / profile
fintrack values.csv        -> balance_snapshots
fintrack value-changes.csv -> account_events
real estate condition      -> property account + mortgage liability + mortgage_profile
```

## Phase 1: Backend import service

Add a backend module:

```text
backend/app/importers/fintrack.py
```

Core responsibilities:

1. Scan a directory for `*-condition.toml`.
2. For each condition file, infer the asset/account name.
3. Load the matching:
   - `{name}-values.csv`
   - `{name}-value-changes.csv`
4. Convert records into Netwise models.
5. Return an import summary.

Proposed structure:

```python
@dataclass
class FintrackImportSummary:
    accounts_created: int
    snapshots_created: int
    events_created: int
    properties_created: int
    mortgages_created: int
    skipped: list[str]
    warnings: list[str]
```

## Phase 2: File mapping rules

### Liquid / normal asset condition

Map `{name}-condition.toml` to:

```text
Account(
  name=name,
  account_kind="asset",
  category=derived category,
  liquidity_class=derived liquidity,
  institution_name=None,
  currency="USD",
)
```

If `fintrack` has an expected yield field, import it later once Netwise has an account-yield model. For now, preserve it in warnings or metadata once metadata exists.

Current blocker: `Account` does not yet have a yield column, so yield import should either wait or require a schema addition.

### Values CSV

Map rows from `{name}-values.csv` to:

```text
BalanceSnapshot(
  household_id=household_id,
  account_id=account.id,
  as_of_date=row.date,
  balance=row.value,
  source="imported_csv",
)
```

Rules:

- Positive balances for assets.
- Positive balances for liabilities too, because account kind determines net-worth sign.
- Use `source="imported_csv"`.
- Use existing unique constraint `(account_id, as_of_date)` for idempotency.

Import behavior should be one of:

```text
skip_existing
replace_existing
fail_on_duplicate
```

Default should be:

```text
skip_existing
```

### Value changes CSV

Map rows from `{name}-value-changes.csv` to:

```text
AccountEvent(
  household_id=household_id,
  account_id=account.id,
  event_date=row.date,
  amount=row.amount,
  event_type=derived event type,
  description=row.description,
  projection_behavior="historical_and_projection" or "historical_only",
)
```

Default mapping:

| fintrack change | Netwise event |
| --- | --- |
| positive cashflow into account | `contribution` |
| negative cashflow out of account | `withdrawal` |
| real estate sale | `asset_sale` if detectable |
| unknown/manual | `manual_projection_adjustment` |

Initial importer can use `manual_projection_adjustment` for ambiguous rows and preserve the original description.

## Phase 3: Real estate import

`fintrack` real estate currently combines:

```text
property value
loan/mortgage condition
amortization
```

Netwise splits this into:

```text
property asset account
mortgage liability account
real_estate_properties profile
mortgage_profiles profile
```

### Real estate property mapping

Create:

```text
Account(
  name="{name}",
  account_kind="asset",
  category="real_estate",
  liquidity_class="illiquid",
)
```

Then create:

```text
RealEstateProperty(
  account_id=property_account.id,
  purchase_date=condition.purchase_date,
  purchase_price=condition.purchase_price,
  down_payment=condition.down_payment,
  expected_appreciation_rate=condition.expected_appreciation_rate,
  property_tax_annual=condition.property_tax_annual,
  insurance_annual=condition.insurance_annual,
  maintenance_rate=condition.maintenance_rate,
  hoa_monthly=condition.hoa_monthly,
)
```

Map property value history from `{name}-values.csv` to property account `BalanceSnapshot` rows.

### Mortgage mapping

If the `fintrack` condition includes loan information, create a separate liability account:

```text
Account(
  name="{name} Mortgage",
  account_kind="liability",
  category="mortgage",
  liquidity_class="debt",
)
```

Then create:

```text
MortgageProfile(
  liability_account_id=mortgage_account.id,
  property_account_id=property_account.id,
  original_principal=condition.loan_principal,
  interest_rate=condition.interest_rate,
  term_months=condition.term_months,
  start_date=condition.loan_start_date,
  monthly_payment=condition.monthly_payment,
  rate_type="fixed",
)
```

Optional initial balance snapshot:

```text
BalanceSnapshot(
  account_id=mortgage_account.id,
  as_of_date=loan_start_date,
  balance=original_principal,
  source="imported_csv",
)
```

Or, if `fintrack` has computed historical loan balances, import those as mortgage balance snapshots.

## Phase 4: Import API

Add backend route:

```text
POST /imports/fintrack
```

Request:

```json
{
  "household_id": "uuid",
  "source_path": "/data/imports/fintrack",
  "duplicate_policy": "skip_existing",
  "dry_run": true
}
```

Response:

```json
{
  "dry_run": true,
  "accounts_created": 3,
  "snapshots_created": 120,
  "events_created": 8,
  "properties_created": 1,
  "mortgages_created": 1,
  "warnings": []
}
```

Important: because this is Dockerized, the import path should be inside a mounted container path, not an arbitrary host path.

Example compose mount later:

```yaml
backend:
  volumes:
    - ./imports:/data/imports:ro
```

Then a user can place fintrack data here:

```text
./imports/fintrack/
```

and the backend sees:

```text
/data/imports/fintrack/
```

## Phase 5: CLI helper

Before building UI, add a backend CLI command for easier testing:

```bash
docker compose exec backend python -m app.importers.fintrack \
  --household-id <uuid> \
  --source-path /data/imports/fintrack \
  --dry-run
```

Then real import:

```bash
docker compose exec backend python -m app.importers.fintrack \
  --household-id <uuid> \
  --source-path /data/imports/fintrack
```

This is better than starting with frontend UI because import debugging is easier from CLI.

## Phase 6: Frontend import UI

Once the backend importer works, add an “Import” section to the frontend.

Minimal UI:

```text
Fintrack import
[Household selector]
[Source path input: /data/imports/fintrack]
[Dry run] [Import]
```

Show summary:

```text
Accounts created: 5
Snapshots created: 234
Events created: 12
Warnings:
- Skipped 2021 brokerage snapshot; duplicate date already exists.
- Yield assumption found but not imported yet.
```

## Phase 7: Idempotency and safety

Importer should be safe to run multiple times.

### Accounts

Find existing account by:

```text
household_id + name + account_kind
```

If it exists, reuse it.

### Balance snapshots

Use existing uniqueness:

```text
account_id + as_of_date
```

Default duplicate behavior:

```text
skip_existing
```

### Events

There is no uniqueness constraint on events right now.

Initial dedupe rule should be application-level:

```text
account_id + event_date + amount + event_type + description
```

Later, add a database uniqueness constraint if needed.

### Profiles

Real estate profile already has unique account constraint:

```text
uq_real_estate_properties_account
```

Mortgage profile already has unique liability account constraint:

```text
uq_mortgage_profiles_liability_account
```

So importer should reuse/update existing profiles.

## Phase 8: Tests

Add tests in:

```text
backend/tests/test_fintrack_importer.py
```

Test fixtures:

```text
backend/tests/fixtures/fintrack/basic/
backend/tests/fixtures/fintrack/real_estate/
```

Test cases:

1. Imports one liquid asset.
2. Imports values CSV as balance snapshots.
3. Imports value changes CSV as account events.
4. Imports real estate as property account.
5. Imports mortgage as liability account plus mortgage profile.
6. Dry run creates nothing.
7. Running import twice does not duplicate snapshots.
8. Duplicate policy works.

## Proposed implementation order

### Commit 1

```text
feat: add fintrack importer service
```

Includes:

- parser
- dry run support
- liquid account import
- value snapshot import
- backend tests

### Commit 2

```text
feat: import fintrack real estate and mortgages
```

Includes:

- property profile mapping
- mortgage liability account mapping
- mortgage profile mapping
- tests

### Commit 3

```text
feat: expose fintrack import endpoint
```

Includes:

- `POST /imports/fintrack`
- request/response schemas
- API tests

### Commit 4

```text
feat: add fintrack import UI
```

Includes:

- frontend import form
- dry run preview
- import summary display

## Recommendation

Start with the backend importer and CLI/dry-run path first.

Suggested next task:

```text
feat: add fintrack importer dry-run
```

That gives a safe foundation before mutating the database.
