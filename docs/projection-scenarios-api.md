# Projection scenario API

Projection scenarios are named, independently editable sets of future-planning inputs. Current balances, historical snapshots, household people, physical account/property identity, mortgages, and annual tax records remain shared household facts.

## Client selection contract

Supported interactive clients **should always send an explicit scenario ID** for scenario-aware planning reads, writes, and projection runs. The bundled React frontend enforces this in its TypeScript API signatures and includes the selected scenario in its TanStack Query keys.

Netwise permanently supports omitted `scenario_id` values as a baseline convenience on endpoints where the OpenAPI query or payload field is optional. Omission resolves to the requested household's single baseline scenario when the operation requires scenario ownership. This policy keeps older API clients and simple baseline-only integrations working without making their data household-wide again. Responses still include the resolved `scenario_id`, allowing clients to become explicit on their next request.

The omission fallback does not apply when:

- an endpoint identifies a scenario in its path;
- a comparison request is made, because `scenario_ids` must contain two to four explicit IDs.

Updates and deletes that identify an existing scenario-owned record by resource ID do not need a second scenario parameter. The server derives and authorizes the record's household and scenario ownership.

## Discover scenarios

```http
GET /households/{household_id}/projection-scenarios
```

The response always contains one item with `is_baseline: true`. Use that ID for explicit baseline operations.

## Scenario-aware endpoints

Pass `scenario_id` as a query parameter for:

- `GET|POST /income-sources`
- `GET|POST /social-security-estimates`
- `GET|POST /spending-items`
- `GET|POST /projection-transfers`
- `GET|PUT /projection-settings/{household_id}`
- `GET|POST /real-estate/sales`
- `GET /real-estate/liquidation-strategies`
- `PUT|DELETE /real-estate/liquidation-strategies/{property_account_id}`
- `GET /households/{household_id}/events`
- `GET /dashboard/{household_id}/projection`

Scenario assumption endpoints put the scenario ID in the path:

```http
GET /projection-scenarios/{scenario_id}/account-assumptions
PUT /projection-scenarios/{scenario_id}/account-assumptions/{account_id}
GET /projection-scenarios/{scenario_id}/property-assumptions
PUT /projection-scenarios/{scenario_id}/property-assumptions/{property_account_id}
```

### Explicit projection example

```http
GET /dashboard/{household_id}/projection?scenario_id={scenario_id}&start_year=2026&end_year=2046&interval=annual
```

The response includes `scenario_id` and `scenario_name` so a result remains attributable even if the client selection changes while the calculation runs.

### Explicit planning write example

```http
POST /spending-items?scenario_id={scenario_id}
Content-Type: application/json

{
  "household_id": "{household_id}",
  "name": "Core living costs",
  "category": "living",
  "annual_amount": "48000.00"
}
```

## Comparison

```http
POST /dashboard/{household_id}/projection-comparison
Content-Type: application/json

{
  "scenario_ids": ["{scenario_id_1}", "{scenario_id_2}"],
  "start_year": 2026,
  "end_year": 2046,
  "interval": "annual"
}
```

`scenario_ids` must contain two to four unique IDs owned by the household. The response preserves request order and includes each complete projection plus server-computed summary metrics. Comparisons are read-only and available to household viewers. Supplying a scenario from another household fails generically without disclosing that scenario's name or data.

## Account-event ownership

Account-event behavior determines whether a scenario ID is valid:

- `historical_only`: `scenario_id` is null and the event never enters a projection.
- `historical_and_projection`: `scenario_id` is null and the shared event enters every scenario.
- `projection_only`: the stored event requires a scenario and enters only that scenario. Supported clients send `scenario_id`; omission by a compatibility client resolves to the baseline.

Scenario-specific historical events are intentionally unsupported.

## Built-in data workflows

- The React frontend sends explicit IDs for scenario-aware operations.
- Demo seeding creates and updates baseline planning inputs intentionally and also creates a named conservative scenario for comparison.
- FinTrack import updates shared current facts and synchronizes imported planning assumptions into the baseline scenario; it does not overwrite non-baseline scenarios.
- Household JSON export includes scenario definitions and all scenario-owned planning inputs so ownership remains attributable.
