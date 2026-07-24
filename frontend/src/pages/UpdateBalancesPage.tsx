import { type FormEvent, useState } from 'react';
import type { Account, HouseholdSnapshot } from '../api';
import { useHouseholdSnapshots, useSnapshotMutations } from '../queries/household';
import { formatMoney } from '../utils/format';

type SnapshotEditDraft = {
  id: string;
  as_of_date: string;
  balance: string;
};

export function UpdateBalancesPage({
  householdId,
  accounts,
  latestBalanceByAccountId,
  defaultDate,
}: {
  householdId: string;
  accounts: Account[];
  latestBalanceByAccountId: ReadonlyMap<string, string | null>;
  defaultDate: string;
}) {
  const [snapshotBatchMessage, setSnapshotBatchMessage] = useState('');
  const [snapshotAccountFilter, setSnapshotAccountFilter] = useState('');
  const [snapshotEditDraft, setSnapshotEditDraft] = useState<SnapshotEditDraft | null>(null);
  const [error, setError] = useState('');
  const snapshotsQuery = useHouseholdSnapshots(householdId, snapshotAccountFilter);
  const snapshotMutations = useSnapshotMutations(householdId);
  const householdSnapshots = snapshotsQuery.data ?? [];

  async function handleCreateSnapshotBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    setError('');
    setSnapshotBatchMessage('');
    const form = new FormData(target);
    const snapshots = accounts
      .map((account) => ({
        account_id: account.id,
        balance: String(form.get(`balance:${account.id}`) ?? '').trim(),
      }))
      .filter((snapshot) => snapshot.balance !== '');
    if (snapshots.length === 0) {
      setError('Enter at least one account balance for the snapshot date.');
      return;
    }

    try {
      const result = await snapshotMutations.createBatch.mutateAsync({
        as_of_date: String(form.get('as_of_date')),
        currency: 'USD',
        snapshots,
      });
      target.reset();
      setSnapshotBatchMessage(
        `Saved ${result.created_count} new and ${result.updated_count} updated snapshot${result.snapshots.length === 1 ? '' : 's'}.`,
      );
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function handleCreateSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setError('');
    try {
      await snapshotMutations.createOne.mutateAsync({
        accountId: String(form.get('account_id')),
        payload: {
          as_of_date: String(form.get('as_of_date')),
          balance: String(form.get('balance')),
          currency: 'USD',
        },
      });
      target.reset();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function handleUpdateSnapshot(snapshot: HouseholdSnapshot) {
    if (snapshotEditDraft?.id !== snapshot.id) return;
    setError('');
    try {
      await snapshotMutations.update.mutateAsync({
        snapshot,
        payload: {
          as_of_date: snapshotEditDraft.as_of_date,
          balance: snapshotEditDraft.balance,
          currency: snapshot.currency,
        },
      });
      setSnapshotEditDraft(null);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function handleDeleteSnapshot(snapshot: HouseholdSnapshot) {
    if (!window.confirm(`Delete ${snapshot.account_name} snapshot from ${snapshot.as_of_date}?`)) {
      return;
    }
    setError('');
    try {
      await snapshotMutations.remove.mutateAsync(snapshot);
      if (snapshotEditDraft?.id === snapshot.id) setSnapshotEditDraft(null);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      <section className="card">
        <h2>Add household snapshot</h2>
        <p className="muted">Capture a snapshot day across many accounts. Empty balances are skipped; existing same-day snapshots are updated.</p>
        {accounts.length ? (
          <form onSubmit={handleCreateSnapshotBatch} className="stacked-form">
            <label>
              Snapshot date
              <input name="as_of_date" type="date" defaultValue={defaultDate} required />
            </label>
            <div className="snapshot-batch-table">
              <div className="snapshot-batch-header">Account</div>
              <div className="snapshot-batch-header">Latest balance</div>
              <div className="snapshot-batch-header">New balance</div>
              {accounts.map((account) => (
                <div className="snapshot-batch-row" key={account.id}>
                  <div>
                    <strong>{account.name}</strong>
                    <span>{account.account_kind} · {account.category}</span>
                  </div>
                  <div>{formatMoney(latestBalanceByAccountId.get(account.id))}</div>
                  <input
                    name={`balance:${account.id}`}
                    inputMode="decimal"
                    placeholder="Leave blank to skip"
                    aria-label={`${account.name} new balance`}
                  />
                </div>
              ))}
            </div>
            <button type="submit" disabled={snapshotMutations.isPending}>Save household snapshot</button>
            {snapshotBatchMessage && <p className="success-message" role="status">{snapshotBatchMessage}</p>}
          </form>
        ) : (
          <p className="muted">Add accounts before capturing a household snapshot.</p>
        )}
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Snapshot history</h2>
            <p className="muted">Review, correct, or delete the balance snapshots that drive current status and trends.</p>
          </div>
          <select
            value={snapshotAccountFilter}
            onChange={(event) => setSnapshotAccountFilter(event.target.value)}
            aria-label="Filter snapshot history by account"
          >
            <option value="">All accounts</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </select>
        </div>
        {snapshotsQuery.isPending ? (
          <p className="muted" role="status">Loading snapshot history…</p>
        ) : snapshotsQuery.error ? (
          <div className="error" role="alert">{String(snapshotsQuery.error)}</div>
        ) : householdSnapshots.length ? (
          <table className="spaced-table" tabIndex={0}>
            <thead>
              <tr>
                <th>Date</th>
                <th>Account</th>
                <th>Balance</th>
                <th>Source</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {householdSnapshots.map((snapshot) => {
                const isEditing = snapshotEditDraft?.id === snapshot.id;
                return (
                  <tr key={snapshot.id}>
                    <td>
                      {isEditing ? (
                        <input
                          type="date"
                          aria-label={`Snapshot date for ${snapshot.account_name}`}
                          value={snapshotEditDraft.as_of_date}
                          onChange={(event) =>
                            setSnapshotEditDraft({ ...snapshotEditDraft, as_of_date: event.target.value })
                          }
                        />
                      ) : (
                        snapshot.as_of_date
                      )}
                    </td>
                    <td>
                      {snapshot.account_name}
                      <span className="muted cell-detail">{snapshot.account_kind} · {snapshot.account_category}</span>
                    </td>
                    <td>
                      {isEditing ? (
                        <input
                          inputMode="decimal"
                          aria-label={`Snapshot balance for ${snapshot.account_name}`}
                          value={snapshotEditDraft.balance}
                          onChange={(event) =>
                            setSnapshotEditDraft({ ...snapshotEditDraft, balance: event.target.value })
                          }
                        />
                      ) : (
                        formatMoney(snapshot.balance)
                      )}
                    </td>
                    <td>{snapshot.source}</td>
                    <td>
                      <div className="action-row">
                        {isEditing ? (
                          <>
                            <button type="button" disabled={snapshotMutations.isPending} onClick={() => handleUpdateSnapshot(snapshot)}>Save</button>
                            <button type="button" className="secondary-button" onClick={() => setSnapshotEditDraft(null)}>
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() =>
                                setSnapshotEditDraft({
                                  id: snapshot.id,
                                  as_of_date: snapshot.as_of_date,
                                  balance: snapshot.balance,
                                })
                              }
                            >
                              Edit
                            </button>
                            <button type="button" className="danger-button" disabled={snapshotMutations.isPending} onClick={() => handleDeleteSnapshot(snapshot)}>
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="muted">No snapshots found for this household/filter.</p>
        )}
      </section>

      <section className="card">
        <h2>Add a single snapshot</h2>
        <p className="muted">Use this for a one-off account update. For routine updates, capture the household snapshot above.</p>
        <form onSubmit={handleCreateSnapshot} className="stacked-form">
          <label>
            Account
            <select name="account_id" required defaultValue="">
              <option value="" disabled>Select account</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>{account.name}</option>
              ))}
            </select>
          </label>
          <label>
            Snapshot date
            <input name="as_of_date" type="date" defaultValue={defaultDate} required />
          </label>
          <label>
            Balance
            <input name="balance" inputMode="decimal" placeholder="100000.00" required />
          </label>
          <button type="submit" disabled={snapshotMutations.isPending}>Add snapshot</button>
        </form>
      </section>
    </>
  );
}
