# Projection Strategy Architecture

## Status

**Baseline boundaries implemented.** Persistence queries and SQLAlchemy-to-domain
mapping live in `backend/app/analytics/projection_input.py`, which returns a
plain-data `ProjectionInput` snapshot. The deterministic engine consumes only
plain records and returns an immutable `ProjectionResult`; API response mapping
lives separately in `backend/app/analytics/projection_results.py`. The default
withdrawal, spending, income, return, tax, and property-sale decisions have also
been extracted into focused policy modules. Strategy registration, scenarios,
and result provenance remain future work described below.

## Context

Netwise currently has one deterministic projection implementation in
`backend/app/analytics/projections.py`. It successfully keeps projection math
outside API routes and supports configurable assumptions such as account yields,
spending, income, tax records, mortgages, real-estate appreciation, and dated
account events.

The projection engine now consumes plain domain records, resolves settings, and
coordinates extracted calculation policies. It returns typed simulation records
rather than constructing API dictionaries. Timeline-level behavior still owned
by the deterministic strategy includes:

- event and transaction ordering within each period;
- recurring-transfer execution and taxable-basis movement;
- automatic property-sale schedule scoring; and
- annual, quarterly, or monthly simulation timing.

These boundaries preserve the first deterministic engine while making policy
alternatives less invasive. A whole-strategy change—such as Monte Carlo returns
or materially different timeline semantics—would still require the explicit
strategy interface and provenance work described below.

## Goals

- Preserve the current deterministic projection as the stable baseline.
- Allow strategies and policies to be added without editing unrelated
  projection behavior.
- Keep API routes and persistence details out of projection calculations.
- Make assumptions, strategy versions, and scenario selection visible in a
  result so it can be reproduced and explained.
- Support scenario-specific events and assumptions correctly.

## Non-goals

- Building a general third-party plugin system for financial strategies.
- Replacing all deterministic projection behavior at once.
- Storing arbitrary executable strategy code in the database.

A small in-process registry of application-owned strategies is sufficient until
there is a demonstrated need for more.

## Implemented boundary

`load_projection_input()` is now the only projection-specific persistence
loader. It resolves active accounts, starting balances, profiles, sales,
events, income, transfers, spending, settings, tax rate, and cost bases before
the deterministic calculation begins. Optimization candidates reuse the same
frozen `ProjectionInput` container. The route-facing
`calculate_net_worth_projection()` function remains a compatibility adapter.
`calculate_projection_from_input()` runs the in-memory strategy and passes its
typed `ProjectionResult` to `format_projection_result()`. Optimization candidates
run the private typed-result strategy directly, so API dictionaries do not enter
simulation or schedule scoring.

Accounts, projection events, income sources, recurring transfers, spending
items, settings, mortgage/property profiles, property sales, and automatic
liquidation strategies are immutable plain-data records. Collection inputs are
tuples where ordering is significant. SQLAlchemy entities are mapped at the
`load_projection_input()` boundary and do not enter the deterministic engine.

## Target structure

```text
backend/app/analytics/
  projection/
    contracts.py       # input, output, assumptions, and protocols
    input_loader.py    # SQLAlchemy -> plain ProjectionInput
    engine.py          # shared timeline orchestration, if applicable
    registry.py        # explicit application-owned strategy registry
    strategies/
      deterministic.py
      monte_carlo.py   # future
    policies/
      returns.py
      spending.py
      tax.py
      withdrawals.py
```

The exact module boundaries may evolve. The important boundaries are:

1. **Input loading:** database access and scenario resolution.
2. **Strategy:** whole-projection algorithm (deterministic vs. stochastic,
   annual vs. monthly, etc.).
3. **Policies:** replaceable decisions within a strategy, such as spending,
   returns, tax, and withdrawal ordering.
4. **Presentation:** API schemas and route concerns.

## Contracts

Strategies should receive plain, immutable inputs rather than a SQLAlchemy
`Session`. A conceptual interface is:

```python
class ProjectionStrategy(Protocol):
    key: str
    version: str

    def project(
        self,
        inputs: ProjectionInput,
        assumptions: ProjectionAssumptions,
    ) -> ProjectionResult: ...
```

`ProjectionInput` should contain the resolved starting balances, active
accounts, profiles, income sources, tax history, and relevant events. It should
not expose persistence operations.

`ProjectionResult` should retain the current point/cash-flow/account detail,
and additionally identify:

- `strategy_key`;
- `strategy_version`;
- `scenario_id`, if any; and
- resolved assumptions used for the calculation.

The baseline strategy should use typed assumptions. A versioned JSON field can
be used for strategy-specific persisted configuration only when a typed model is
not shared across strategies.

## Real-estate sales are transactions, not withdrawals

A property must not be reduced like a liquid account to fund ordinary spending.
A future `WithdrawalPolicy` may choose to sell real estate, but it must produce
a discrete property-sale transaction rather than invoke the generic account
withdrawal code.

Introduce a first-class `RealEstateSale` (or equivalently named
`PropertySaleEvent`) associated with a property account. It should contain:

- household and property-account IDs;
- sale date and gross sale price;
- an optional, validated `proceeds_account_id`;
- selling-cost rate and/or an explicit selling-cost amount;
- the linked mortgage payoff treatment; and
- explicit tax treatment or a documented initial exclusion from tax modelling.

At the sale date, the engine should:

1. remove the full projected property balance from the property account;
2. pay the linked mortgage's projected outstanding balance and set that
   liability balance to zero;
3. deduct selling costs and any explicitly modelled taxes;
4. transfer the remaining cash proceeds to a designated active asset account;
5. record each leg as an explainable projection cash flow.

The default proceeds account should be the first **non-retirement liquid**
asset under the selected funding policy. If none exists, require an explicit
proceeds account instead of silently placing sale proceeds in retirement or
another property. A user-selected proceeds account overrides that default, but
must belong to the household and be an active asset account.

A sale can result in a shortfall when sale proceeds do not cover the mortgage
payoff and costs. That shortfall should be funded through the normal withdrawal
policy, excluding the sold property, and should be represented explicitly in
the result. The engine must not leave a negative property balance or continue
mortgage amortization after sale.

The existing `asset_sale` account event is insufficient for this purpose: it
has no proceeds target, sale-price/cost fields, or mortgage-payoff semantics.
Keep it for generic asset-sale adjustments or migrate it deliberately; do not
interpret it as a property sale by account category alone.

## Composable policies

Not every change warrants a distinct whole-projection strategy. The baseline
deterministic strategy should compose focused policies:

| Policy | Examples |
| --- | --- |
| `ReturnModel` | fixed account yield, category default, stochastic annual return |
| `SpendingModel` | explicit spending, historical estimate, retirement spending rule |
| `TaxModel` | effective-rate approximation, tax-bracket model |
| `WithdrawalPolicy` | liquidity-first, taxable-first, retirement-first, user-defined order |

The default account-pool withdrawal policy now lives in
`backend/app/analytics/projection_withdrawals.py`. It owns deterministic funding
priority, preferred-account cutoff behavior, taxable and capital-gains drag,
cost-basis reduction, liquidation expenses, and the resulting account cash-flow
legs. These decisions have focused unit coverage independent of timeline
orchestration.

`_withdraw_from_assets()` coordinates automatic property sales between
non-retirement and retirement funding attempts. Transaction eligibility,
individual sale application, and candidate schedule generation are delegated to
`projection_property_sales.py`; whole-run coordination remains in the
deterministic strategy.

The baseline spending policy now lives in
`backend/app/analytics/projection_spending.py`. It owns inflation growth,
working-to-retirement transitions, itemized spending, owner property tax and
insurance, and scheduled owner mortgage payments. Shared active-month and
amortized-payment calculations also live there so rental orchestration can reuse
the same timing rules without duplicating them.

Income timing now lives in `backend/app/analytics/projection_income.py`. The
policy annualizes supported pay frequencies, applies default or source-specific
growth, enforces source start and end dates, and allocates annualized income
evenly across active months. The explicit period-width argument is retained so
a future payroll scheduler can replace monthly spreading without changing the
engine boundary.

The deterministic return model now lives in
`backend/app/analytics/projection_returns.py`. It resolves property appreciation,
explicit account assumptions, category defaults, zero-return liabilities, and
the fallback return in the existing precedence order. It also converts effective
annual returns to monthly or quarterly returns and applies the result to account
balances with the engine's existing cent rounding.

Effective-rate tax treatment now lives in
`backend/app/analytics/projection_tax.py`. It nets rental expenses against
ordinary and rental income, computes effective-rate income tax, aggregates
ordinary withdrawal tax with capital-gains and explicit taxes, and calculates
property-sale tax from net gain or the documented gross-price fallback. The
missing-property-basis warning is colocated with that fallback decision.
Account-level taxable withdrawal and cost-basis mechanics remain in the
withdrawal policy, which supplies the tax components consumed here.

Property-sale transactions now live in
`backend/app/analytics/projection_property_sales.py`. The policy applies property
removal, linked mortgage payoff, selling expenses, sale tax, proceeds transfer,
taxable-account basis updates, and shortfall delegation as explicit transaction
legs. It also owns automatic-sale eligibility and ordered March candidate
schedules. The deterministic strategy retains whole-projection schedule scoring
and repeated candidate execution because those coordinate complete engine runs,
not an individual sale transaction.

Simulation output records and API response formatting now live in
`backend/app/analytics/projection_results.py`. The engine and optimizer exchange
immutable account, cash-flow, point, optimization, and top-level result records.
Only the public compatibility boundary converts those records to the existing
API dictionary shape, which keeps response naming and collection conversion out
of timeline simulation while preserving the endpoint contract.

## Scenario semantics

`AccountEvent` already has a nullable `scenario_id`, but the current projection
endpoint does not accept one and the projection query does not filter by one.
A future scenario design must make the selection explicit:

- `scenario_id = NULL` means a baseline event and is included for every run.
- For a scenario run, include baseline events plus events with that scenario's
  ID.
- Do not include events belonging to other scenarios.
- A baseline run includes only baseline events unless product requirements
  explicitly define another behavior.

Introduce a `ProjectionScenario` entity before exposing scenario selection. It
should at least hold household ownership, name, selected strategy key, strategy
assumptions, and timestamps. Household-wide defaults may remain useful, but
scenario overrides must be resolved into the immutable input/assumptions passed
to a strategy.

## Migration plan

1. **Characterize existing behavior.** Preserve and extend the current
   projection tests as golden regression coverage.
2. **Extract input loading.** Move database queries and settings resolution from
   `calculate_net_worth_projection()` into an input loader that creates plain
   inputs.
3. **Wrap the current engine.** Implement `DeterministicProjectionStrategy`
   using the current annual behavior unchanged. Keep the existing endpoint as a
   compatibility adapter.
4. **Extract policies.** Move withdrawal, tax, return, and spending decisions
   behind focused interfaces, beginning with `WithdrawalPolicy`.
5. **Implement scenarios.** Add scenario persistence, API selection, strict
   event filtering, and scenario-specific assumptions.
6. **Expose provenance.** Include strategy/version/scenario and resolved
   assumptions in results.
7. **Add alternatives deliberately.** Add a historical spending model or a
   second withdrawal policy first; add Monte Carlo only once output contracts
   can support distributions rather than a single deterministic value.

## Testing expectations

- Contract tests should run against every `ProjectionStrategy`.
- Each policy should have focused unit tests using only plain inputs.
- The baseline deterministic strategy needs golden tests proving its results
  remain unchanged during extraction.
- Scenario tests must demonstrate baseline inclusion, matching-scenario
  inclusion, and exclusion of unrelated scenario events.
- Result metadata should be tested so displayed forecasts can be traced to the
  assumptions and algorithm that produced them.

## Current implementation references

- Plain input records: `backend/app/analytics/projection_contracts.py`
- Input loader and immutable aggregate: `backend/app/analytics/projection_input.py`
- Typed simulation results and API formatter: `backend/app/analytics/projection_results.py`
- Deterministic in-memory entry point: `calculate_projection_from_input()` in `backend/app/analytics/projections.py`
- Route-facing persistence adapter: `calculate_net_worth_projection()` in `backend/app/analytics/projections.py`
- Projection endpoint: `backend/app/api/routes/dashboard.py`
- Household settings: `backend/app/db/models.py` (`ProjectionSettings`)
- Event scenario field: `backend/app/db/models.py` (`AccountEvent.scenario_id`)
- Existing coverage: `backend/tests/test_projection.py`
- Original product direction: `docs/technical-design.md`
