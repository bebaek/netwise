# Agent API access

Netwise supports household-bound personal API tokens for privacy-conscious AI agents and
other local automation. Tokens use the existing REST API and OpenAPI schema; an
agent does not need access to the browser session cookie or the user's password.

## Security model

- A token belongs to one user and exactly one household.
- Only a SHA-256 digest is stored. The full token is returned once at creation.
- Tokens expire after 1 to 365 days and can be revoked at any time.
- `finance:read` permits read-only household finance endpoints.
- `finance:write` permits only the account balance snapshot-batch endpoint. Use it with
  `finance:read` when the MCP adapter must resolve account names and inspect existing snapshots.
- `projections:run` additionally permits the projection-comparison POST endpoint.
- Tokens cannot access user, household-member, import, export, authentication, or
  token-management endpoints.
- All other writes are rejected, regardless of the token's household role. The MCP balance
  tool requires an exact preview confirmation, but the client agent is responsible for waiting
  for that text in a subsequent user message rather than generating it itself.
- Authenticated token requests are audited with the token identity, endpoint, optional
  MCP tool name, result status, and duration. Request and response bodies are not logged.

API tokens should still be treated as secrets because finance reads contain sensitive
information. Keep Netwise on a trusted network, pass the token through a secret store
or environment variable, and do not put it in an agent prompt, repository, command
history, or log output. Confirm the privacy policy of any hosted model before allowing
it to process Netwise responses.

## Create a token

Token management requires a normal browser session. In the Netwise frontend, open
**Settings**, select the intended household, and use **AI agent access** to create,
review, or revoke tokens. The underlying endpoints are:

```text
GET    /api-tokens
GET    /api-tokens/audit-events?household_id={household_id}
POST   /api-tokens
DELETE /api-tokens/{token_id}
```

For a production Compose deployment reached through the frontend proxy, prefix these
paths with `/api`. For local backend development, use them directly on port 8001.

The creation request is:

```json
{
  "name": "Local finance agent",
  "household_id": "HOUSEHOLD_UUID",
  "scopes": ["finance:read", "finance:write", "projections:run"],
  "expires_in_days": 30
}
```

The response contains a `token` beginning with `nwt_`. Save it immediately: later list
responses contain only its non-secret prefix and metadata.

For command-line setup, sign in to an HTTPS deployment and retain the session cookie:

```bash
curl --fail --silent --show-error \
  --cookie-jar netwise-cookie.txt \
  --header 'Content-Type: application/json' \
  --data '{"email":"you@example.com","password":"YOUR_PASSWORD"}' \
  https://netwise.example/api/auth/login

curl --fail --silent --show-error \
  --cookie netwise-cookie.txt \
  --header 'Content-Type: application/json' \
  --data '{
    "name":"Local finance agent",
    "household_id":"HOUSEHOLD_UUID",
    "scopes":["finance:read","finance:write","projections:run"],
    "expires_in_days":30
  }' \
  https://netwise.example/api/api-tokens

rm -f netwise-cookie.txt
```

Avoid placing a real password directly in a shared script. The example is intended to
show the request flow, not prescribe credential storage.

## Call the API

Send the token as a bearer credential:

```bash
export NETWISE_TOKEN='nwt_REPLACE_WITH_THE_ONE_TIME_SECRET'

curl --fail --silent --show-error \
  --header "Authorization: Bearer ${NETWISE_TOKEN}" \
  https://netwise.example/api/households/HOUSEHOLD_UUID
```

Useful agent operations include:

- `GET /households` — returns only the token-bound household.
- `GET /accounts?household_id=HOUSEHOLD_UUID` — account metadata.
- `GET /households/HOUSEHOLD_UUID/snapshots` — recent balances.
- `GET /dashboard/HOUSEHOLD_UUID/net-worth` — current financial summary.
- `GET /projection-scenarios?household_id=HOUSEHOLD_UUID` — available scenarios.
- `POST /households/HOUSEHOLD_UUID/snapshot-batch` — records account balances when the
  token has `finance:write`.
- `POST /dashboard/HOUSEHOLD_UUID/projection-comparison` — deterministic scenario
  comparison when the token has `projections:run`.

The machine-readable API contract is available from `/openapi.json` in backend
development or `/api/openapi.json` through the production proxy. Give that schema and
the deployment base URL to an OpenAPI-capable agent, but provide the bearer token via
the agent's secret configuration rather than conversational context.

## Use the MCP adapter

The backend includes a local stdio MCP server and an authenticated multitenant Streamable HTTP
endpoint hosted by FastAPI. See
[Multitenant HTTP MCP Architecture](multitenant-mcp-architecture.md). The authenticated HTTP
endpoint exposes these compact semantic tools:

- `summarize_financial_position` — totals, account coverage, and category allocation
  without account names.
- `explain_net_worth_change` — category-level drivers between two requested dates.
- `list_projection_scenarios` — scenario names and IDs for discovery within the
  token-bound household.
- `summarize_projection_assumptions` — selectable settings, income, spending,
  account-return, property, transfer, and tax sections for a scenario selected by name or ID.
- `get_property_projection_parameters` — detailed property, rental, mortgage, sale, and
  automatic-liquidation inputs for one named property and scenario.
- `check_projection_readiness` — scenario-specific errors and warnings for missing balances,
  settings, tax history, and property inputs.
- `summarize_projection_comparison` — key outcomes for two to four scenarios selected by name
  or ID, without yearly points or account-level projection details.
- `check_financial_data_freshness` — stale or missing snapshots; this tool includes
  affected account names so the user knows what to update.
- `record_account_balance` — previews one create/update, returns exact confirmation text,
  and writes only when the user supplies that text verbatim in a subsequent message. It requires
  both `finance:read` and `finance:write`.

The projection-planning reads and comparison require both `finance:read` and
`projections:run`. Scenario selectors accept either an exact UUID or an unambiguous,
case-insensitive name; omitting the selector from a single-scenario tool uses the baseline.

Lower-level read tools remain available over the stdio adapter when details are necessary:

- `get_financial_summary`
- `list_accounts`
- `list_recent_balances`
- `get_net_worth_history`
- `list_projection_scenarios`
- `compare_projection_scenarios`

The adapters discover the household from the bound token, so the model does not choose
or supply a household ID. They expose read tools, deterministic projection comparison, and the
single confirmed balance-snapshot mutation described above; they do not expose other Netwise
mutation endpoints. The HTTP tools call shared household-scoped application services directly.
The stdio adapter receives REST responses locally and reduces them before returning semantic
summaries to the model.

Run it from a checkout:

```bash
cd /path/to/netwise/backend
NETWISE_API_URL=https://netwise.example/api \
NETWISE_API_TOKEN='nwt_REPLACE_WITH_THE_ONE_TIME_SECRET' \
uv run --extra agent python -m app.agent.mcp_server
```

A typical stdio MCP client configuration is:

```json
{
  "mcpServers": {
    "netwise": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/netwise/backend",
        "run",
        "--extra",
        "agent",
        "python",
        "-m",
        "app.agent.mcp_server"
      ],
      "env": {
        "NETWISE_API_URL": "https://netwise.example/api",
        "NETWISE_API_TOKEN": "nwt_REPLACE_WITH_THE_ONE_TIME_SECRET"
      }
    }
  }
}
```

MCP client configuration formats differ, so adapt the outer structure for the chosen
client. Restrict permissions on configuration files containing the token. The optional
`NETWISE_API_TIMEOUT_SECONDS` setting defaults to 30 seconds. Netwise's MCP adapter
also labels requests with the tool name so **Settings → AI agent access → Recent agent
activity** can distinguish semantic tool calls from direct API requests.

## Multitenant HTTP deployment

The deployed MCP transport is an authenticated `/mcp` endpoint in the Netwise FastAPI process,
normally exposed as `/api/mcp/` by the production proxy. Each MCP client sends its own
household-bound Netwise API token as a bearer credential. Authentication derives the household
and scopes for every tool invocation; no process-global MCP client or household context is
permitted.

REST routes and MCP tools call shared household-scoped application services rather than the HTTP
MCP implementation making loopback REST requests. Tool authorization is scope-based at execution
time, and tool identity is added to audit context by the server. The local stdio adapter remains
supported. The full decision, security invariants, alternatives, migration sequence, and
verification requirements are in
[Multitenant HTTP MCP Architecture](multitenant-mcp-architecture.md).
