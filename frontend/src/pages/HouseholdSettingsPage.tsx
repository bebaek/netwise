import type { FormEventHandler } from 'react';
import type { FintrackImportResult, Household, HouseholdMembership, User } from '../api';

export function HouseholdSettingsPage({
  household,
  members,
  availableUsers,
  adminToolsEnabled,
  onDownloadExport,
  onCreateHousehold,
  onCreateUser,
  onRemoveMember,
  onAddMember,
  fintrackDryRun,
  onFintrackDryRun,
  onImportFintrack,
  fintrackImportResult,
}: {
  household: Household;
  members: HouseholdMembership[];
  availableUsers: User[];
  adminToolsEnabled: boolean;
  onDownloadExport: () => void | Promise<void>;
  onCreateHousehold: FormEventHandler<HTMLFormElement>;
  onCreateUser: FormEventHandler<HTMLFormElement>;
  onRemoveMember: (userId: string) => void | Promise<void>;
  onAddMember: FormEventHandler<HTMLFormElement>;
  fintrackDryRun: boolean;
  onFintrackDryRun: (dryRun: boolean) => void;
  onImportFintrack: FormEventHandler<HTMLFormElement>;
  fintrackImportResult: FintrackImportResult | null;
}) {
  return (
    <>
      <section className="card">
        <div className="section-header">
          <div>
            <h2>People & household access</h2>
            <p className="muted">Switch users, switch households, and manage household memberships.</p>
          </div>
          <div className="management-actions">
            {adminToolsEnabled && (
              <button type="button" className="secondary-button" onClick={onDownloadExport}>
                Download household JSON
              </button>
            )}
            <form onSubmit={onCreateHousehold} className="form-row">
              <input name="name" placeholder="New household name" required />
              <button type="submit">Add household</button>
            </form>
            <form onSubmit={onCreateUser} className="form-row">
              <input name="display_name" placeholder="New user name" required />
              <input name="email" type="email" placeholder="Email (optional)" />
              <button type="submit">Add user</button>
            </form>
          </div>
        </div>
        <div className="member-list">
          {members.map((membership) => (
            <div key={membership.id} className="member-row">
              <span>
                <strong>{membership.user?.display_name ?? membership.user_id}</strong>
                <span className="muted"> {membership.user?.email ?? ''}</span>
              </span>
              <span className="pill">{membership.role}</span>
              <button type="button" className="secondary-button" onClick={() => onRemoveMember(membership.user_id)}>
                Remove
              </button>
            </div>
          ))}
        </div>
        {availableUsers.length > 0 && (
          <form onSubmit={onAddMember} className="form-row spaced-table">
            <select name="user_id" required defaultValue="">
              <option value="" disabled>Add user to household</option>
              {availableUsers.map((user) => (
                <option key={user.id} value={user.id}>{user.display_name}</option>
              ))}
            </select>
            <select name="role" defaultValue="member">
              <option value="owner">Owner</option>
              <option value="admin">Admin</option>
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
            </select>
            <button type="submit">Add member</button>
          </form>
        )}
      </section>

      {adminToolsEnabled && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>Import FinTrack data</h2>
              <p className="muted">
                Import a server-local FinTrack data directory into {household.name}. Expected files: <code>*-condition.toml</code>, <code>*-values.csv</code>, and optional <code>*-value-changes.csv</code>.
              </p>
            </div>
          </div>
          <form onSubmit={onImportFintrack} className="form-row">
            <input name="data_dir" placeholder="/Users/burm/code/fintrack/data-me" required />
            <input name="currency" placeholder="USD" defaultValue="USD" maxLength={3} />
            <label className="inline-toggle">
              <input
                name="dry_run"
                type="checkbox"
                checked={fintrackDryRun}
                onChange={(event) => onFintrackDryRun(event.target.checked)}
              />
              Dry run
            </label>
            <button type="submit">{fintrackDryRun ? 'Preview import' : 'Import for real'}</button>
          </form>
          {fintrackImportResult && (
            <div className="import-result">
              <p>
                <strong>{fintrackImportResult.dry_run ? 'Dry run' : 'Import'} complete:</strong>{' '}
                {fintrackImportResult.accounts_created} accounts created, {fintrackImportResult.accounts_existing} existing, {fintrackImportResult.snapshots_created} snapshots created, {fintrackImportResult.snapshots_updated} updated, {fintrackImportResult.snapshots_existing} unchanged, {fintrackImportResult.events_created} events created, {fintrackImportResult.events_existing} existing.
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Kind</th>
                      <th>Accounts</th>
                      <th>Snapshots</th>
                      <th>Events</th>
                      <th>Profiles</th>
                      <th>Warnings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fintrackImportResult.assets.map((asset) => (
                      <tr key={asset.name}>
                        <td>{asset.name}</td>
                        <td>{asset.kind}</td>
                        <td>{asset.accounts_created} created / {asset.accounts_existing} existing</td>
                        <td>{asset.snapshots_created} created / {asset.snapshots_updated} updated / {asset.snapshots_existing} unchanged</td>
                        <td>{asset.events_created} created / {asset.events_existing} existing</td>
                        <td>{asset.real_estate_profiles_created + asset.mortgage_profiles_created} created / {asset.real_estate_profiles_existing + asset.mortgage_profiles_existing} existing</td>
                        <td>{asset.warnings.join('; ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}
    </>
  );
}
