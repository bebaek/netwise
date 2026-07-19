import type { FormEventHandler } from 'react';
import type { Account, HouseholdSnapshot } from '../api';
import { formatMoney } from '../utils/format';

export type SnapshotEditDraft = {
  id: string;
  as_of_date: string;
  balance: string;
};

export function UpdateBalancesPage({
  accounts,
  latestBalanceByAccountId,
  defaultDate,
  snapshotBatchMessage,
  onCreateSnapshotBatch,
  householdSnapshots,
  snapshotAccountFilter,
  onSnapshotAccountFilter,
  snapshotEditDraft,
  onSnapshotEditDraft,
  onUpdateSnapshot,
  onDeleteSnapshot,
  onCreateSnapshot,
}: {
  accounts: Account[];
  latestBalanceByAccountId: ReadonlyMap<string, string | null>;
  defaultDate: string;
  snapshotBatchMessage: string;
  onCreateSnapshotBatch: FormEventHandler<HTMLFormElement>;
  householdSnapshots: HouseholdSnapshot[];
  snapshotAccountFilter: string;
  onSnapshotAccountFilter: (accountId: string) => void;
  snapshotEditDraft: SnapshotEditDraft | null;
  onSnapshotEditDraft: (draft: SnapshotEditDraft | null) => void;
  onUpdateSnapshot: (snapshot: HouseholdSnapshot) => void | Promise<void>;
  onDeleteSnapshot: (snapshot: HouseholdSnapshot) => void | Promise<void>;
  onCreateSnapshot: FormEventHandler<HTMLFormElement>;
}) {
  return (
    <>
      <section className="card">
        <h2>Add household snapshot</h2>
        <p className="muted">Capture a snapshot day across many accounts. Empty balances are skipped; existing same-day snapshots are updated.</p>
        {accounts.length ? (
          <form onSubmit={onCreateSnapshotBatch} className="stacked-form">
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
            <button type="submit">Save household snapshot</button>
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
            onChange={(event) => onSnapshotAccountFilter(event.target.value)}
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
        {householdSnapshots.length ? (
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
                            onSnapshotEditDraft({ ...snapshotEditDraft, as_of_date: event.target.value })
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
                            onSnapshotEditDraft({ ...snapshotEditDraft, balance: event.target.value })
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
                            <button type="button" onClick={() => onUpdateSnapshot(snapshot)}>Save</button>
                            <button type="button" className="secondary-button" onClick={() => onSnapshotEditDraft(null)}>
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() =>
                                onSnapshotEditDraft({
                                  id: snapshot.id,
                                  as_of_date: snapshot.as_of_date,
                                  balance: snapshot.balance,
                                })
                              }
                            >
                              Edit
                            </button>
                            <button type="button" className="danger-button" onClick={() => onDeleteSnapshot(snapshot)}>
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
        <form onSubmit={onCreateSnapshot} className="stacked-form">
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
          <button type="submit">Add snapshot</button>
        </form>
      </section>
    </>
  );
}
