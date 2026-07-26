import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from 'react';
import type { ApiToken, ApiTokenCreated, ApiTokenScope, Household } from '../api';
import {
  useApiTokenAuditEvents,
  useApiTokenMutations,
  useApiTokens,
} from '../queries/apiTokens';

function formatTimestamp(value: string | null): string {
  if (!value) return 'Never';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function tokenStatus(token: ApiToken): 'active' | 'expired' | 'revoked' {
  if (token.revoked_at) return 'revoked';
  return new Date(token.expires_at).getTime() <= Date.now() ? 'expired' : 'active';
}

export function ApiTokenSettings({ household }: { household: Household }) {
  const tokensQuery = useApiTokens();
  const auditQuery = useApiTokenAuditEvents(household.id);
  const mutations = useApiTokenMutations();
  const [error, setError] = useState('');
  const [createdToken, setCreatedToken] = useState<ApiTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const secretPanelRef = useRef<HTMLDivElement>(null);
  const tokens = (tokensQuery.data ?? []).filter(
    (token) => token.household_id === household.id,
  );
  const auditEvents = auditQuery.data ?? [];

  useEffect(() => {
    setCreatedToken(null);
    setCopied(false);
  }, [household.id]);

  useEffect(() => {
    if (createdToken) secretPanelRef.current?.focus();
  }, [createdToken]);

  async function onCreateToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const scopes: ApiTokenScope[] = ['finance:read'];
    if (form.get('finance_write') === 'on') scopes.push('finance:write');
    if (form.get('projections_run') === 'on') scopes.push('projections:run');
    setError('');
    setCreatedToken(null);
    setCopied(false);
    try {
      const token = await mutations.createToken.mutateAsync({
        name: String(form.get('name') ?? '').trim(),
        household_id: household.id,
        scopes,
        expires_in_days: Number(form.get('expires_in_days')),
      });
      setCreatedToken(token);
      target.reset();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onCopyToken() {
    if (!createdToken) return;
    setError('');
    try {
      await navigator.clipboard.writeText(createdToken.token);
      setCopied(true);
    } catch (copyError: unknown) {
      setError(`Could not copy the token: ${String(copyError)}`);
    }
  }

  async function onRevokeToken(token: ApiToken) {
    if (!window.confirm(`Revoke API token “${token.name}”? Agents using it will immediately lose access.`)) {
      return;
    }
    setError('');
    try {
      await mutations.revokeToken.mutateAsync(token.id);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <section className="card">
      <div className="section-header">
        <div>
          <h2>AI agent access</h2>
          <p className="muted">
            Create a household-bound token for a local MCP or OpenAPI agent. Tokens can
            expose sensitive balances and planning data, so store them like passwords.
          </p>
        </div>
      </div>

      {error && <div className="error" role="alert">{error}</div>}
      {tokensQuery.error && (
        <div className="error" role="alert">{String(tokensQuery.error)}</div>
      )}
      {auditQuery.error && (
        <div className="error" role="alert">{String(auditQuery.error)}</div>
      )}

      <form className="api-token-form" onSubmit={onCreateToken}>
        <label>
          Token name
          <input name="name" placeholder="My local finance agent" maxLength={100} required />
        </label>
        <label>
          Expires after
          <span className="input-with-suffix">
            <input
              name="expires_in_days"
              type="number"
              min={1}
              max={365}
              defaultValue={30}
              required
            />
            <span>days</span>
          </span>
        </label>
        <fieldset>
          <legend>Permissions</legend>
          <label className="inline-toggle">
            <input type="checkbox" checked disabled />
            Read household finances
          </label>
          <label className="inline-toggle">
            <input name="finance_write" type="checkbox" />
            Record confirmed account balance snapshots
          </label>
          <label className="inline-toggle">
            <input name="projections_run" type="checkbox" />
            Run deterministic scenario comparisons
          </label>
        </fieldset>
        <p className="muted api-token-form-note">
          The token will be restricted to <strong>{household.name}</strong>. It cannot
          manage users, import or export data, or change records other than confirmed
          account balance snapshots when that permission is selected.
        </p>
        <button type="submit" disabled={mutations.isPending}>
          {mutations.createToken.isPending ? 'Creating token…' : 'Create API token'}
        </button>
      </form>

      {createdToken && (
        <div
          className="token-secret-panel"
          role="alert"
          tabIndex={-1}
          ref={secretPanelRef}
        >
          <h3>Save this token now</h3>
          <p>
            This is the only time Netwise will show the full token. Put it in the
            agent’s secret configuration, not in a prompt or source file.
          </p>
          <label>
            New API token
            <textarea readOnly rows={3} value={createdToken.token} />
          </label>
          <div className="form-row">
            <button type="button" onClick={() => void onCopyToken()}>
              {copied ? 'Copied' : 'Copy token'}
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => setCreatedToken(null)}
            >
              I saved it
            </button>
          </div>
        </div>
      )}

      <div className="section-header api-token-list-heading">
        <div>
          <h3>Tokens for {household.name}</h3>
          <p className="muted">Only the non-secret prefix is shown after creation.</p>
        </div>
      </div>
      {tokensQuery.isPending ? (
        <div role="status">Loading API tokens…</div>
      ) : tokens.length === 0 ? (
        <p className="muted">No API tokens have been created for this household.</p>
      ) : (
        <div className="member-list">
          {tokens.map((token) => {
            const status = tokenStatus(token);
            return (
              <div className="member-row api-token-row" key={token.id}>
                <div>
                  <strong>{token.name}</strong>
                  <div><code>{token.token_prefix}…</code></div>
                  <div className="muted">
                    Expires {formatTimestamp(token.expires_at)} · Last used{' '}
                    {formatTimestamp(token.last_used_at)}
                  </div>
                  <div className="muted">
                    {token.scopes.map((scope) => scope.replace(':', ' ')).join(' · ')}
                  </div>
                </div>
                <span className={`pill token-status-${status}`}>{status}</span>
                {status === 'active' ? (
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={mutations.isPending}
                    onClick={() => void onRevokeToken(token)}
                  >
                    Revoke
                  </button>
                ) : <span />}
              </div>
            );
          })}
        </div>
      )}

      <div className="section-header api-token-list-heading">
        <div>
          <h3>Recent agent activity</h3>
          <p className="muted">
            Requests record the tool or endpoint, result, and timing—not balances,
            request bodies, or response data.
          </p>
        </div>
        <button
          type="button"
          className="secondary-button"
          disabled={auditQuery.isFetching}
          onClick={() => void auditQuery.refetch()}
        >
          {auditQuery.isFetching ? 'Refreshing…' : 'Refresh activity'}
        </button>
      </div>
      {auditQuery.isPending ? (
        <div role="status">Loading agent activity…</div>
      ) : auditEvents.length === 0 ? (
        <p className="muted">No API-token requests have been recorded for this household.</p>
      ) : (
        <div className="audit-event-list">
          {auditEvents.map((event) => {
            const successful = event.status_code >= 200 && event.status_code < 400;
            return (
              <div className="audit-event-row" key={event.id}>
                <div>
                  <strong>{event.tool_name ?? event.path}</strong>
                  {event.tool_name && <div><code>{event.path}</code></div>}
                  <div className="muted">
                    {event.token_name} · <code>{event.token_prefix}…</code>
                  </div>
                </div>
                <div className="muted audit-event-time">
                  {formatTimestamp(event.created_at)}
                </div>
                <span className={`pill ${successful ? 'token-status-active' : 'token-status-revoked'}`}>
                  {event.method} {event.status_code}
                </span>
                <span className="muted">{event.duration_ms} ms</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
