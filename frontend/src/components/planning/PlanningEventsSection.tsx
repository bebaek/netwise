import { useState, type FormEvent } from 'react';
import type { Account, AccountEvent } from '../../api';
import { useAccountEventMutations, useHouseholdAccountEvents } from '../../queries/household';
import { formatMoney } from '../../utils/format';

type AccountEventDraft = {
  id?: string;
  original_account_id?: string;
  account_id: string;
  event_date: string;
  amount: string;
  currency: string;
  event_type: string;
  description: string;
  projection_behavior: string;
};

const ACCOUNT_EVENT_TYPE_OPTIONS = [
  ['contribution', 'Contribution'],
  ['withdrawal', 'Withdrawal'],
  ['transfer', 'Transfer'],
  ['large_purchase', 'Large purchase'],
  ['asset_sale', 'Asset sale'],
  ['gift', 'Gift'],
  ['inheritance', 'Inheritance'],
  ['tax_payment', 'Tax payment'],
  ['account_added', 'Account added'],
  ['account_removed', 'Account removed'],
  ['manual_projection_adjustment', 'Manual projection adjustment'],
] as const;

const PROJECTION_BEHAVIOR_OPTIONS = [
  ['projection_only', 'Projection only'],
  ['historical_and_projection', 'Historical and projection'],
  ['historical_only', 'Historical only'],
] as const;

function eventTypeLabel(value: string): string {
  return ACCOUNT_EVENT_TYPE_OPTIONS.find(([optionValue]) => optionValue === value)?.[1] ?? value;
}

function projectionBehaviorLabel(value: string): string {
  return PROJECTION_BEHAVIOR_OPTIONS.find(([optionValue]) => optionValue === value)?.[1] ?? value;
}

export function PlanningEventsSection({
  householdId,
  scenarioId,
  defaultDate,
  accounts,
  accountNameById,
}: {
  householdId: string;
  scenarioId: string;
  defaultDate: string;
  accounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
}) {
  const [draft, setDraft] = useState<AccountEventDraft | null>(null);
  const [error, setError] = useState('');
  const eventsQuery = useHouseholdAccountEvents(householdId, scenarioId);
  const mutations = useAccountEventMutations(householdId, scenarioId);
  const events = eventsQuery.data ?? [];

  function startNewDraft() {
    setDraft({
      account_id: accounts[0]?.id ?? '',
      event_date: defaultDate,
      amount: '',
      currency: 'USD',
      event_type: 'manual_projection_adjustment',
      description: '',
      projection_behavior: 'projection_only',
    });
  }

  function startEditDraft(accountEvent: AccountEvent) {
    setDraft({
      id: accountEvent.id,
      original_account_id: accountEvent.account_id,
      account_id: accountEvent.account_id,
      event_date: accountEvent.event_date,
      amount: accountEvent.amount,
      currency: accountEvent.currency,
      event_type: accountEvent.event_type,
      description: accountEvent.description ?? '',
      projection_behavior: accountEvent.projection_behavior,
    });
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    setError('');
    const payload = {
      account_id: draft.account_id,
      event_date: draft.event_date,
      amount: draft.amount,
      currency: draft.currency,
      event_type: draft.event_type,
      description: draft.description || null,
      projection_behavior: draft.projection_behavior,
      scenario_id: draft.projection_behavior === 'projection_only' ? scenarioId : undefined,
    };
    try {
      if (draft.id && draft.original_account_id) {
        await mutations.update.mutateAsync({
          accountId: draft.original_account_id,
          eventId: draft.id,
          payload,
        });
      } else {
        await mutations.create.mutateAsync({
          accountId: draft.account_id,
          payload: {
            event_date: payload.event_date,
            amount: payload.amount,
            currency: payload.currency,
            event_type: payload.event_type,
            description: draft.description || undefined,
            projection_behavior: payload.projection_behavior,
            scenario_id: payload.scenario_id,
          },
        });
      }
      setDraft(null);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function handleDelete(accountEvent: AccountEvent) {
    if (!window.confirm(`Delete ${accountEvent.event_type} event from ${accountEvent.event_date}?`)) {
      return;
    }
    setError('');
    try {
      await mutations.remove.mutateAsync(accountEvent);
      if (draft?.id === accountEvent.id) setDraft(null);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      <section className="card projection-events-card">
        <div className="section-header">
          <div>
            <h2>Projection events</h2>
            <p className="muted">Capture planned future contributions, withdrawals, purchases, sales, and adjustments.</p>
          </div>
          <button type="button" onClick={startNewDraft} disabled={!accounts.length}>
            Add event
          </button>
        </div>

        {draft && (
          <form onSubmit={handleSave} className="event-editor-card">
            <div className="section-header">
              <div>
                <h3>{draft.id ? 'Edit projection event' : 'Add projection event'}</h3>
                <p className="muted">Use positive amounts; outflow event types are applied as withdrawals in projections.</p>
              </div>
              <button type="button" className="secondary-button" onClick={() => setDraft(null)}>
                Cancel
              </button>
            </div>
            <div className="event-editor-grid">
              <label>
                Account
                <select
                  required
                  value={draft.account_id}
                  onChange={(event) => setDraft({ ...draft, account_id: event.target.value })}
                >
                  {!draft.account_id && <option value="">Select account</option>}
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>{account.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Event date
                <input
                  required
                  type="date"
                  value={draft.event_date}
                  onChange={(event) => setDraft({ ...draft, event_date: event.target.value })}
                />
              </label>
              <label>
                Amount
                <input
                  required
                  inputMode="decimal"
                  placeholder="2500.00"
                  value={draft.amount}
                  onChange={(event) => setDraft({ ...draft, amount: event.target.value })}
                />
              </label>
              <label>
                Type
                <select
                  required
                  value={draft.event_type}
                  onChange={(event) => setDraft({ ...draft, event_type: event.target.value })}
                >
                  {ACCOUNT_EVENT_TYPE_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label>
                Projection behavior
                <select
                  required
                  value={draft.projection_behavior}
                  onChange={(event) => setDraft({ ...draft, projection_behavior: event.target.value })}
                >
                  {PROJECTION_BEHAVIOR_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label>
                Description
                <input
                  placeholder="Optional note"
                  value={draft.description}
                  onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                />
              </label>
            </div>
            <div className="action-row">
              <button type="submit" disabled={!draft.account_id || mutations.isPending}>Save event</button>
              <button type="button" className="secondary-button" onClick={() => setDraft(null)}>
                Cancel
              </button>
            </div>
          </form>
        )}

        {eventsQuery.isPending ? (
          <p className="muted" role="status">Loading projection events…</p>
        ) : eventsQuery.error ? (
          <div className="error" role="alert">{String(eventsQuery.error)}</div>
        ) : events.length ? (
          <>
            <div className="desktop-table table-frame sticky-actions">
              <table className="editable-table compact-table">
                <thead>
                  <tr>
                    <th>Date</th><th>Account</th><th>Type</th><th>Amount</th>
                    <th>Behavior</th><th>Description</th><th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.id}>
                      <td>{event.event_date}</td>
                      <td>{accountNameById.get(event.account_id) ?? event.account_id}</td>
                      <td>{eventTypeLabel(event.event_type)}</td>
                      <td>{formatMoney(event.amount)}</td>
                      <td>{projectionBehaviorLabel(event.projection_behavior)}</td>
                      <td>{event.description || '—'}</td>
                      <td>
                        <div className="action-row">
                          <button type="button" className="secondary-button" onClick={() => startEditDraft(event)}>
                            Edit
                          </button>
                          <button type="button" className="danger-button" disabled={mutations.isPending} onClick={() => handleDelete(event)}>
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mobile-card-list">
              {events.map((event) => (
                <article className="event-card" key={event.id}>
                  <div className="event-card-header">
                    <div>
                      <strong className="event-card-title">{eventTypeLabel(event.event_type)}</strong>
                      <span>{event.event_date}</span>
                    </div>
                    <strong className="event-card-amount">{formatMoney(event.amount)}</strong>
                  </div>
                  <dl className="event-card-meta">
                    <div>
                      <dt>Account</dt>
                      <dd>{accountNameById.get(event.account_id) ?? event.account_id}</dd>
                    </div>
                    <div>
                      <dt>Behavior</dt>
                      <dd>{projectionBehaviorLabel(event.projection_behavior)}</dd>
                    </div>
                    {event.description && (
                      <div><dt>Description</dt><dd>{event.description}</dd></div>
                    )}
                  </dl>
                  <div className="event-card-actions">
                    <button type="button" className="secondary-button" onClick={() => startEditDraft(event)}>
                      Edit
                    </button>
                    <button type="button" className="danger-button" disabled={mutations.isPending} onClick={() => handleDelete(event)}>
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </>
        ) : (
          <p className="muted">No projection events yet.</p>
        )}
      </section>
    </>
  );
}
