import { useState, type FormEvent, type FormEventHandler } from 'react';
import type { FintrackImportResult, Household } from '../api';
import { ApiTokenSettings } from '../components/ApiTokenSettings';
import { useHouseholdMembers } from '../queries/household';
import {
  useHouseholdSettingsData,
  useHouseholdSettingsMutations,
} from '../queries/householdSettings';

function exportFilename(name: string): string {
  const safeName = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '') || 'household';
  return `netwise-${safeName}-export-${new Date().toISOString().slice(0, 10)}.json`;
}

function downloadJson(filename: string, value: unknown): void {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function HouseholdSettingsPage({
  household,
  authenticatedUserId,
  onCreateHousehold,
  onCurrentUserRemoved,
}: {
  household: Household;
  authenticatedUserId: string;
  onCreateHousehold: FormEventHandler<HTMLFormElement>;
  onCurrentUserRemoved: () => void | Promise<void>;
}) {
  const [error, setError] = useState('');
  const [fintrackDryRun, setFintrackDryRun] = useState(true);
  const [fintrackImportResult, setFintrackImportResult] = useState<FintrackImportResult | null>(null);
  const membersQuery = useHouseholdMembers(household.id);
  const settingsData = useHouseholdSettingsData();
  const mutations = useHouseholdSettingsMutations(household.id);
  const members = membersQuery.data ?? [];
  const users = settingsData.users.data ?? [];
  const capabilities = settingsData.capabilities.data;
  const currentRole = members.find(
    (membership) => membership.user_id === authenticatedUserId,
  )?.role ?? 'viewer';
  const availableUsers = users.filter(
    (user) => !members.some((membership) => membership.user_id === user.id),
  );
  const adminToolsEnabled = capabilities?.admin_tools_enabled ?? false;
  const fintrackImportEnabled = capabilities?.fintrack_import_enabled ?? false;

  async function onCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const displayName = String(form.get('display_name') ?? '').trim();
    const email = String(form.get('email') ?? '').trim();
    if (!displayName) return;
    setError('');
    try {
      await mutations.createHouseholdUser.mutateAsync({
        display_name: displayName,
        email: email || undefined,
      });
      target.reset();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onAddMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setError('');
    try {
      await mutations.addMember.mutateAsync({
        user_id: String(form.get('user_id') ?? '').trim(),
        role: String(form.get('role') ?? '').trim(),
      });
      target.reset();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onRemoveMember(userId: string) {
    setError('');
    try {
      await mutations.removeMember.mutateAsync(userId);
      if (userId === authenticatedUserId) await onCurrentUserRemoved();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onDownloadExport() {
    setError('');
    try {
      const result = await mutations.downloadExport.mutateAsync();
      downloadJson(exportFilename(household.name), result);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onImportFintrack(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!fintrackDryRun) {
      const confirmed = window.confirm(
        `Import FinTrack data into ${household.name}? This will write accounts, snapshots, and events to the database.`,
      );
      if (!confirmed) return;
    }
    setError('');
    setFintrackImportResult(null);
    try {
      const result = await mutations.importData.mutateAsync({
        household_id: household.id,
        data_dir: String(form.get('data_dir') ?? '').trim(),
        currency: String(form.get('currency') ?? '').trim() || undefined,
        dry_run: fintrackDryRun,
      });
      setFintrackImportResult(result);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      {membersQuery.error && <div className="error" role="alert">{String(membersQuery.error)}</div>}
      {settingsData.users.error && (
        <div className="error" role="alert">{String(settingsData.users.error)}</div>
      )}
      {settingsData.capabilities.error && (
        <div className="error" role="alert">{String(settingsData.capabilities.error)}</div>
      )}
      {(membersQuery.isPending || settingsData.users.isPending || settingsData.capabilities.isPending) && (
        <div className="card" role="status">Loading household settings…</div>
      )}
      <section className="card">
        <div className="section-header">
          <div>
            <h2>People & household access</h2>
            <p className="muted">Review household access and manage memberships permitted by your role.</p>
          </div>
          <div className="management-actions">
            {adminToolsEnabled && ['owner', 'admin'].includes(currentRole) && (
              <button
                type="button"
                className="secondary-button"
                disabled={mutations.isPending}
                onClick={onDownloadExport}
              >
                Download household JSON
              </button>
            )}
            <form onSubmit={onCreateHousehold} className="form-row">
              <input name="name" placeholder="New household name" required />
              <button type="submit">Add household</button>
            </form>
            {['owner', 'admin'].includes(currentRole) && (
              <form onSubmit={onCreateUser} className="form-row">
                <input name="display_name" placeholder="New user name" required />
                <input name="email" type="email" placeholder="Email (optional)" />
                <button type="submit" disabled={mutations.isPending}>Add user</button>
              </form>
            )}
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
              {['owner', 'admin'].includes(currentRole)
                && (currentRole === 'owner' || membership.role !== 'owner') && (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={mutations.isPending}
                  onClick={() => onRemoveMember(membership.user_id)}
                >
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
        {['owner', 'admin'].includes(currentRole) && availableUsers.length > 0 && (
          <form onSubmit={onAddMember} className="form-row spaced-table">
            <select name="user_id" aria-label="Household member" required defaultValue="">
              <option value="" disabled>Add user to household</option>
              {availableUsers.map((user) => (
                <option key={user.id} value={user.id}>{user.display_name}</option>
              ))}
            </select>
            <select name="role" aria-label="Household role" defaultValue="member">
              {currentRole === 'owner' && <option value="owner">Owner</option>}
              <option value="admin">Admin</option>
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
            </select>
            <button type="submit" disabled={mutations.isPending}>Add member</button>
          </form>
        )}
      </section>

      <ApiTokenSettings household={household} />

      {fintrackImportEnabled && ['owner', 'admin'].includes(currentRole) && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>Import FinTrack data</h2>
              <p className="muted">
                Import a directory beneath the configured FinTrack import root into {household.name}. Expected files: <code>*-condition.toml</code>, <code>*-values.csv</code>, and optional <code>*-value-changes.csv</code>.
              </p>
            </div>
          </div>
          <form onSubmit={onImportFintrack} className="form-row">
            <input name="data_dir" placeholder="portfolio" required />
            <input name="currency" placeholder="USD" defaultValue="USD" maxLength={3} />
            <label className="inline-toggle">
              <input
                name="dry_run"
                type="checkbox"
                checked={fintrackDryRun}
                onChange={(event) => setFintrackDryRun(event.target.checked)}
              />
              Dry run
            </label>
            <button type="submit" disabled={mutations.isPending}>
              {fintrackDryRun ? 'Preview import' : 'Import for real'}
            </button>
          </form>
          {fintrackImportResult && (
            <div className="import-result">
              <p>
                <strong>{fintrackImportResult.dry_run ? 'Dry run' : 'Import'} complete:</strong>{' '}
                {fintrackImportResult.accounts_created} accounts created, {fintrackImportResult.accounts_existing} existing, {fintrackImportResult.snapshots_created} snapshots created, {fintrackImportResult.snapshots_updated} updated, {fintrackImportResult.snapshots_existing} unchanged, {fintrackImportResult.events_created} events created, {fintrackImportResult.events_existing} existing.
              </p>
              <div className="table-scroll">
                <table tabIndex={0}>
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
