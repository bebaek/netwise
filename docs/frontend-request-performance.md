# Frontend API request performance

This document records reproducible API request counts for representative frontend workflows. The automated measurement is `frontend/tests/e2e/request-counts.spec.ts`; its JSON attachment contains the method-and-path breakdown for each run.

## Measurement method

- Browser: Playwright desktop Chromium, 1440 × 1000 viewport
- Server: isolated Docker Compose E2E stack using the seeded demo household
- Frontend: Vite development server with React Strict Mode enabled
- Counted traffic: requests whose URL path starts with `/api/`
- Initial-load boundary: an authenticated page reload through a fully loaded Overview page
- Scenario boundary: immediately before the user action through Playwright's network-idle state
- Baseline application commit: `70dbbca` (projection scenario comparison milestone)

React Strict Mode intentionally re-runs mount behavior in the development build, so many initial-load requests appear twice. The scenario comparisons use the same environment before and after the change.

## Results

| Scenario | Baseline | First query-cache slice | Route-owned snapshots | Route-owned events | Route-owned asset real estate | Route-owned planning real estate | Route-owned budget data | Route-owned people data | Route-owned projection config | Route-owned settings data | Reduction from baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial authenticated workspace load | 50 | 46 | 44 | 42 | 36 | 32 | 28 | 22 | 18 | 14 | 72% |
| Change snapshot account filter | 18 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 94% |
| Toggle interpolated history | 24 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 96% |
| Save one household snapshot | 19 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 74% |

Current request budgets added after the original baseline:

| Scenario | Current requests | Request set |
| --- | ---: | --- |
| Create an account | 5 | Mutation, accounts, net worth, historical trend, and breakdown history |
| Enter Planning and load route data | 21 observed, 22 maximum | Shared planning data, scenario list, and selected-scenario collections; development Strict Mode may issue a second mount request |
| Run a two-scenario comparison | 1 | One comparison request; the response contains both complete projections and summaries |
| Create an account event | 2 | Event mutation and household account-events refresh |
| Enter Assets and load property data | 6 | Properties, analytics, and mortgages; each doubled by development Strict Mode |
| Create a property without a valuation | 8 | Two mutations plus targeted account, financial-summary, property, and analytics refreshes |
| Create a planned property sale | 2 | Sale mutation and planned-sales refresh |
| Create a spending item | 2 | Spending mutation and spending-items refresh |
| Create a household person | 2 | Person mutation and household-people refresh |
| Create a recurring transfer | 2 | Transfer mutation and projection-transfers refresh |
| Save projection settings | 1 | Settings mutation with direct query-cache update |
| Enter Settings and load route data | 4 | Users and capabilities; each doubled by development Strict Mode |
| Create a user | 1 | User mutation with direct query-cache update |
| Add a household member | 2 | Membership mutation and members refresh |

## Interpretation

The first slice moved accounts, household account events, snapshots, net worth, historical trend, and breakdown history into TanStack Query. Subsequent route-owned slices moved snapshots into `UpdateBalancesPage`; all planning collections and their mutations into `PlanningPage`; real-estate assets into `AssetsPage`; and user administration, capabilities, membership mutations, imports, and exports into `HouseholdSettingsPage`. Overview now fetches none of those route-only collections; each loads on demand when its route mounts. Household membership remains a shared top-level query because the current role applies throughout the workspace. Snapshot filters request only filtered snapshots, and interpolation changes request only historical trend data.

The central `refreshDashboard()` path has been removed. The Vite/Strict Mode test environment invokes mount behavior twice, and the household events batch endpoint replaces six account-specific requests with one logical route query when Planning mounts.

## Regression expectations

The Playwright measurement test enforces these stable request boundaries:

- Snapshot account filtering makes exactly one API request, to household snapshots.
- Toggling interpolation makes exactly one API request, to historical trend.
- Saving a household snapshot makes no more than five API requests and does not reload planning, real-estate, membership, mortgage, income, or tax collections.
- Account creation makes no more than five API requests and does not reload unrelated route domains.
- Entering Planning requests only its shared and selected-scenario route collections, with a maximum of 22 requests in the Strict Mode measurement environment.
- Running a scenario comparison makes exactly one request; changing chart or table presentation does not trigger more projection calls.
- Account-event creation makes two requests: the mutation and one batched event refresh.
- Planned property-sale creation makes two requests: the mutation and one sales refresh.
- Spending-item creation makes two requests: the mutation and one spending-items refresh.
- Household-person creation makes two requests: the mutation and one household-people refresh.
- Recurring-transfer creation makes two requests: the mutation and one projection-transfers refresh.
- Saving projection settings makes one request and updates the query cache from the mutation response.
- Entering Settings requests users and capabilities; membership is already shared by the workspace.
- User creation makes one request and updates the query cache from the mutation response.
- Adding a household member makes two requests: the mutation and one members refresh.
- Entering Assets requests only properties, property analytics, and mortgages for the real-estate asset domain.
- Property creation avoids unrelated planning, membership, tax, sales, and mortgage collection refreshes.
- Initial Overview loading does not issue per-account event requests and fetches none of the migrated route-only collections.

Future frontend slices should append results to the table rather than replacing the original baseline.
