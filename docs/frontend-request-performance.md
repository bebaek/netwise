# Frontend API request performance

This document records reproducible API request counts for representative frontend workflows. The automated measurement is `frontend/tests/e2e/request-counts.spec.ts`; its JSON attachment contains the method-and-path breakdown for each run.

## Measurement method

- Browser: Playwright desktop Chromium, 1440 × 1000 viewport
- Server: isolated Docker Compose E2E stack using the seeded demo household
- Frontend: Vite development server with React Strict Mode enabled
- Counted traffic: requests whose URL path starts with `/api/`
- Initial-load boundary: an authenticated page reload through a fully loaded Overview page
- Scenario boundary: immediately before the user action through Playwright's network-idle state
- Baseline application commit: `1fb66d9`

React Strict Mode intentionally re-runs mount behavior in the development build, so many initial-load requests appear twice. The scenario comparisons use the same environment before and after the change.

## Results

| Scenario | Baseline | First query-cache slice | Route-owned snapshots | Route-owned events | Reduction from baseline |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial authenticated workspace load | 50 | 46 | 44 | 42 | 16% |
| Change snapshot account filter | 18 | 1 | 1 | 1 | 94% |
| Toggle interpolated history | 24 | 1 | 1 | 1 | 96% |
| Save one household snapshot | 19 | 5 | 5 | 5 | 74% |

Current request budgets added after the original baseline:

| Scenario | Current requests | Request set |
| --- | ---: | --- |
| Create an account | 5 | Mutation, accounts, net worth, historical trend, and breakdown history |
| Enter Planning and load account events | 2 | Household account events only; doubled by development Strict Mode |
| Create an account event | 2 | Event mutation and household account-events refresh |

## Interpretation

The first slice moved accounts, household account events, snapshots, net worth, historical trend, and breakdown history into TanStack Query. Subsequent route-owned slices moved snapshots into `UpdateBalancesPage` and account events into `PlanningPage`, including their local drafts and mutations. Overview now fetches neither snapshots nor account events; each loads on demand when its route mounts. Snapshot filters request only filtered snapshots, and interpolation changes request only historical trend data. Saving a household snapshot performs one mutation followed by four relevant refreshes: snapshots, net worth, historical trend, and breakdown history.

The initial-load improvement is still limited because most remaining domains are loaded centrally by `App.refreshDashboard()`, and the Vite/Strict Mode test environment invokes mount behavior twice. The household events batch endpoint replaces six account-specific requests with one logical route query when Planning mounts.

## Regression expectations

The Playwright measurement test enforces these stable request boundaries:

- Snapshot account filtering makes exactly one API request, to household snapshots.
- Toggling interpolation makes exactly one API request, to historical trend.
- Saving a household snapshot makes no more than five API requests and does not reload planning, real-estate, membership, mortgage, income, or tax collections.
- Account creation makes no more than five API requests and does not reload unrelated route domains.
- Entering Planning requests only the household account-events endpoint for event data.
- Account-event creation makes two requests: the mutation and one batched event refresh.
- Initial Overview loading does not issue per-account event requests and fetches neither snapshots nor account events.

Future frontend slices should append results to the table rather than replacing the original baseline.
