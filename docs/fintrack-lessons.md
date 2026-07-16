# Lessons from `fintrack`

`fintrack` is a precursor CLI that models personal finance from dated asset values, expected yields, real-estate valuation, and loan amortization. Netwise should preserve the useful ideas while moving to a multi-user database-backed web app.

## Useful concepts to carry forward

### Dated values as the core record

`fintrack` stores each asset's values as dated CSV rows. Netwise should retain this as the core `balance_snapshots` concept.

For real estate, a property valuation is also a dated value. It should be treated as a valuation snapshot with source and confidence metadata.

### Account-level expected yield

`fintrack` attaches a yield to each asset condition and uses it to project future value from the latest known value. Netwise should support account-level yield assumptions in addition to category defaults.

Initial strategy:

- Account-specific static yield when set.
- Category default yield otherwise.
- Scenario override when running projections.

### Value changes as planned or known events

`fintrack` supports `value_changes`, which are dated changes applied during projection. Netwise should model this more explicitly instead of overloading balance snapshots.

Recommended Netwise concept:

```text
AccountEvent
  household_id
  account_id
  event_date
  amount
  event_type
  description
  projection_behavior
```

Example event types:

- Contribution
- Withdrawal
- Transfer
- Large purchase
- Asset sale
- Gift
- Inheritance
- Tax payment
- Account added
- Account removed
- Manual projection adjustment

These events can serve two purposes:

1. Explain historical net worth changes and improve expense estimation.
2. Represent planned future cashflows in projection scenarios.

### Real estate value and mortgage balance

`fintrack` embeds loan condition inside the real estate asset and computes equity as:

```text
property value - computed loan balance
```

Netwise should keep this computation but model it with separate accounts:

- Property asset account for market value snapshots.
- Mortgage liability account for balance snapshots or amortized balance.
- Mortgage profile linking the liability to the property.

This preserves clean balance-sheet modeling while supporting the precursor's useful amortization behavior.

### Projection should be deterministic first

`fintrack` projects by compounding from the latest known dated value and applying dated changes. Netwise should start with the same deterministic approach before adding advanced time-series models.

Baseline projection loop:

1. Start from latest snapshot on or before projection start.
2. Compound by selected yield strategy.
3. Apply dated account events.
4. For real estate, project property value and mortgage balance separately.
5. Aggregate by account kind, category, and liquidity class.

## Differences from `fintrack`

### Multi-user household model

`fintrack` is local and single-user. Netwise should use households/workspaces with memberships and roles.

### Database-backed snapshots

`fintrack` uses files. Netwise should store normalized records in PostgreSQL, while supporting import from file-based sources.

### Explicit liability accounts

`fintrack` real estate includes loan information inside the asset. Netwise should represent liabilities explicitly so mortgages, student loans, credit cards, and other debt are consistently handled.

### Metadata and auditability

Netwise should track source, confidence, created time, updated time, and actor where useful.

This matters especially for:

- Real estate valuations
- Mortgage balances
- Annual tax records
- Manual adjustments
- Plugin-provided data

## Import opportunity

A future importer can read `fintrack` data directories:

```text
{name}-condition.toml
{name}-values.csv
{name}-value-changes.csv
```

Mapping:

- Liquid asset condition -> account yield assumption.
- Real estate condition -> property account, mortgage liability account, mortgage profile.
- Values CSV -> balance or valuation snapshots.
- Value changes CSV -> account events.

This importer would help migrate existing precursor data into Netwise.
