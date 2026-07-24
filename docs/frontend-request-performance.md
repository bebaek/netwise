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

| Scenario | Baseline | First query-cache slice | Route-owned snapshots | Reduction from baseline |
| --- | ---: | ---: | ---: | ---: |
| Initial authenticated workspace load | 50 | 46 | 44 | 12% |
| Change snapshot account filter | 18 | 1 | 1 | 94% |
| Toggle interpolated history | 24 | 1 | 1 | 96% |
| Save one household snapshot | 19 | 5 | 5 | 74% |

## Interpretation

The first slice moved accounts, household account events, snapshots, net worth, historical trend, and breakdown history into TanStack Query. The route-owned snapshot slice then moved snapshot queries, filters, edit drafts, status state, and mutations into `UpdateBalancesPage`. Overview no longer fetches snapshots; entering Update loads them on demand. Snapshot filters request only filtered snapshots, and interpolation changes request only historical trend data. Saving a household snapshot performs one mutation followed by four relevant refreshes: snapshots, net worth, historical trend, and breakdown history.

The initial-load improvement is smaller because most remaining domains are still loaded centrally by `App.refreshDashboard()`, and the Vite/Strict Mode test environment invokes mount effects twice. The household events batch endpoint reduces six account-specific event requests to one endpoint per dashboard load.

## Regression expectations

The Playwright measurement test enforces these stable request boundaries:

- Snapshot account filtering makes exactly one API request, to household snapshots.
- Toggling interpolation makes exactly one API request, to historical trend.
- Saving a household snapshot makes no more than five API requests and does not reload planning, real-estate, membership, mortgage, income, or tax collections.
- Initial Overview loading uses the household events endpoint, does not issue per-account event requests, and does not fetch snapshots.

Future frontend slices should append results to the table rather than replacing the original baseline.
