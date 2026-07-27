# Multitenant HTTP MCP Architecture

## Status

**Proposed.** Netwise currently provides a household-bound stdio MCP adapter that calls the
REST API with one API token from its environment. This document defines the target architecture
for serving MCP over authenticated Streamable HTTP from the Netwise backend process.

## Context

The stdio adapter is appropriate for a local, single-household agent. A deployed Minigent
instance may serve more than one tenant, however, and should not need one Netwise MCP process or
sidecar per household. Embedding a household API token in a shared MCP service would make that
service household-specific and would duplicate credential and deployment management.

Netwise already has the required multitenant security model:

- each personal API token belongs to one user and exactly one household;
- token scopes limit finance reads, balance writes, and projection runs;
- household authorization fails closed and does not reveal other households; and
- token requests are audited without recording request or response bodies.

The MCP interface is a thin, agent-oriented presentation layer over the same financial
operations. It should reuse those guarantees rather than introduce a second tenancy model.

## Decision

Netwise will expose an authenticated Streamable HTTP MCP endpoint from the existing FastAPI
backend process. The internal backend path will be `/mcp`; deployments that proxy backend routes
under `/api` will expose it as `/api/mcp`.

The client supplies a normal Netwise personal API token on the MCP request:

```http
Authorization: Bearer nwt_...
```

The endpoint authenticates the token, derives an immutable request-scoped principal, and makes
that principal available to tool execution. A conceptual principal contains:

```text
api_token_id
user_id
household_id
scopes
token name/prefix for audit metadata
```

The model never supplies or selects a household ID. Tool implementations obtain it only from the
authenticated principal.

```text
Minigent tenant A -- token A --\
                                \
Minigent tenant B -- token B ----> FastAPI /mcp
                                  |  authenticate token per request/session
                                  |  derive household and scopes
                                  |  dispatch approved MCP tool
                                  v
                         shared application services
                                  |
                                  v
                              PostgreSQL

Browser/REST clients ------------> existing REST routes
                                   using the same authorization and services
```

This is a modular-monolith boundary: REST routes and MCP tools are separate presentation
adapters over shared authentication, authorization, and application services. MCP tools should
not make loopback HTTP requests to the REST API when running in the backend process.

## Authentication and authorization

The existing API-token parsing and validation logic should be extracted into a reusable function
or dependency that returns the authenticated token principal. REST authorization can continue to
map HTTP methods and paths to scopes. MCP authorization must instead map each tool directly to its
required scopes because every Streamable HTTP invocation uses the same MCP endpoint and HTTP
method.

Initial scope requirements are:

| MCP tools | Required scopes |
| --- | --- |
| Financial summaries, accounts, balances, history, and freshness | `finance:read` |
| Projection listing and comparison | `finance:read` and, for a comparison run, `projections:run` |
| `record_account_balance` preview and save | `finance:read` and `finance:write` |

Authorization must occur for every tool invocation, not only while listing tools or creating an
MCP session. A token that expires or is revoked during a long-lived session must stop working.
Whether the server advertises only tools allowed by the current token or advertises all tools and
rejects unauthorized calls is an implementation choice; execution-time checks are mandatory in
either case.

Browser session cookies are not accepted for MCP. The endpoint requires bearer-token
authentication so agent access remains independently revocable, scoped, and auditable.

## Tenant isolation

No mutable process-global object may hold the current token, user, household, database session,
or `NetwiseApiClient`. The registered MCP server and tool definitions may be process-global only
when all tenant state is obtained from request context.

If the MCP SDK creates transport sessions, each invocation must still be authenticated. Any
cached session identity must be immutable, bound to the authenticated token ID, and rejected if a
request presents a different token. Prefer stateless operation where supported. Database sessions
remain request-scoped and are never shared between concurrent tool calls.

Application-service methods should accept the authenticated principal or an explicit trusted
`household_id` derived from it. They must not accept a model-provided household ID. Existing
household role checks and the API token's household boundary remain authoritative.

## Application boundaries

The current stdio adapter uses `NetwiseApiClient` to call REST endpoints and computes semantic
summaries from those responses. For in-process HTTP MCP, reusable operations should move behind
application-service functions:

```text
REST route ---------\
                     > application service -> persistence/analytics
HTTP MCP tool ------/
```

The service layer owns input validation, household scoping, projection execution, balance
preview/save behavior, and response construction. Presentation adapters own protocol-specific
mapping and error handling. This avoids both loopback HTTP and direct database logic duplicated in
MCP tools.

The stdio command remains supported for local clients. It may continue using
`NetwiseApiClient`, or become a small remote client for the HTTP MCP endpoint. It must not require
the in-process server to keep a global environment-derived household context.

## Confirmed balance writes

`record_account_balance` remains the only initially exposed mutation. Its safety contract is the
same over stdio and HTTP:

1. A call without confirmation returns a preview and `required_confirmation`; it performs no
   write.
2. The agent shows the preview and stops until a subsequent user message contains the exact
   confirmation text.
3. A changed account, date, balance, currency, action, existing balance, token, or household
   invalidates the prior confirmation.
4. The tool reports success only after persistence completes and returns `status: "saved"`.

Confirmation validation must occur in the household-scoped application service. Confirmation
state must never be shared across tenants. A future enhancement may replace deterministic text
alone with a short-lived, single-use, tenant-bound confirmation challenge; that is not required
to introduce HTTP transport.

## Auditing and privacy

Each MCP tool invocation records:

- API token, user, and household identity;
- stable MCP endpoint path and tool name;
- result status and duration; and
- no request arguments, response body, balances, account names, or confirmation text.

The current `X-Netwise-Agent-Tool` header is useful for the out-of-process REST adapter. The
in-process MCP endpoint should set the tool name in trusted server-side audit context rather than
trusting a client-provided header.

Errors returned through MCP must follow the existing safe API-error policy: enough information to
correct the request, but no household-existence disclosure, stack traces, SQL details, token
metadata, or other tenants' data.

## Deployment and Minigent integration

No Netwise MCP sidecar or separate Deployment is required. The existing backend image, process,
Service, health checks, and scaling policy serve both REST and MCP. Reverse proxies must support
Streamable HTTP behavior and should apply appropriate request-size, idle-timeout, and connection
limits to `/api/mcp`.

Minigent registers one Netwise MCP server and supplies the appropriate household-bound API token
per tenant. Conceptually:

```toml
[[mcp_servers]]
name = "netwise"
url = "https://netwise.example/api/mcp"
headers = { Authorization = "Bearer ${NETWISE_API_TOKEN}" }
allowed_tools = [
  "summarize_financial_position",
  "explain_net_worth_change",
  "summarize_projection_comparison",
  "check_financial_data_freshness",
  "record_account_balance",
]
```

Minigent may combine `netwise`, `home-assistant`, and web search in one `home` capability profile.
Each Minigent tenant must receive its own Netwise token; sharing a token intentionally shares the
same Netwise household boundary.

## Resource isolation

Running MCP in the API process reduces latency and operational complexity but increases shared
resource impact. The HTTP endpoint therefore needs:

- request and tool execution timeouts;
- per-token rate and concurrency limits;
- bounded tool arguments and response sizes;
- cancellation propagation where supported;
- existing projection input limits; and
- metrics that distinguish REST and MCP traffic without financial labels.

If MCP traffic later requires independent scaling or stronger process isolation, the MCP module
can run from the same image as a separate process. It must preserve bearer-token authentication,
request-scoped principals, shared service contracts, and per-tool scope enforcement. That is an
operational change, not a tenancy-model change.

## Alternatives considered

### Netwise MCP sidecar in the Minigent pod

This keeps the adapter private to Minigent but gives the sidecar one embedded household token.
It requires one sidecar/configuration per household and exposes the finance credential in the
Minigent workload. It remains useful as a transitional deployment but is not the target.

### Household-bound MCP Deployment beside Netwise

This isolates MCP from the API process but still requires one configured deployment per household
or a second MCP-specific authentication system. A multitenant separate process remains possible,
but provides little initial value while the MCP layer is a thin facade over API services.

### Literal MCP sidecar in the Netwise API pod

This allows localhost communication but couples replica counts while retaining an extra process
and loopback protocol boundary. Scaling the API would duplicate sidecars, and embedded household
credentials would not support multitenancy.

## Implementation sequence

1. Extract reusable API-token authentication and define an immutable agent principal.
2. Extract household-scoped application services used by both REST and MCP.
3. Refactor MCP tool functions to resolve principal and database state per invocation.
4. Add per-tool scope checks and trusted tool-name audit context.
5. Mount Streamable HTTP MCP into FastAPI while retaining stdio compatibility.
6. Add proxy configuration and Minigent's per-tenant Netwise server configuration.
7. Deploy behind the existing Netwise Service and complete isolation and regression tests.

## Required verification

- Missing, malformed, expired, and revoked bearer tokens are rejected.
- Two concurrent clients with different tokens cannot observe or mutate each other's households.
- A token cannot select a household through tool arguments or crafted MCP payloads.
- Every tool enforces its declared scopes at execution time.
- Revocation takes effect for an existing or subsequent MCP session.
- Balance preview performs no write; exact confirmation saves once in the correct household.
- Changed preview inputs cannot reuse an earlier confirmation.
- MCP audit events contain trusted tool identity but no financial arguments or results.
- Existing REST authorization, stdio MCP behavior, and semantic tool results do not regress.
- Streamable HTTP initialization, tool listing, calls, cancellation, and error mapping work through
  the production proxy.
