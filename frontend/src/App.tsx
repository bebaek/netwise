import { useQueryClient } from '@tanstack/react-query';
import { FormEvent, Suspense, lazy, type ReactNode, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import {
  Account,
  FintrackImportResult,
  Household,
  HouseholdMembership,
  NetWorthProjection,
  ProjectionSettings,
  ProjectionTransfer,
  User,
  addHouseholdMember,
  createHousehold,
  createProjectionTransfer,
  createUser,
  deleteProjectionTransfer,
  exportHousehold,
  getCapabilities,
  getNetWorthProjection,
  getProjectionSettings,
  importFintrack,
  listHouseholds,
  listHouseholdMembers,
  listProjectionTransfers,
  listUsers,
  removeHouseholdMember,
  upsertProjectionSettings,
} from './api';
import {
  AppHeader,
  AppNavigation,
  ViewHeading,
  type AppView,
  type ThemePreference,
} from './components/AppShell';
import {
  householdQueryKeys,
  useAccounts,
  useHouseholdFinancialSummary,
} from './queries/household';
import { formatMoney } from './utils/format';
import './styles.css';

const AssetsPage = lazy(() => import('./pages/AssetsPage').then((module) => ({ default: module.AssetsPage })));
const HouseholdSettingsPage = lazy(() =>
  import('./pages/HouseholdSettingsPage').then((module) => ({ default: module.HouseholdSettingsPage })),
);
const OverviewPage = lazy(() => import('./pages/OverviewPage').then((module) => ({ default: module.OverviewPage })));
const PlanningPage = lazy(() => import('./pages/PlanningPage').then((module) => ({ default: module.PlanningPage })));
const UpdateBalancesPage = lazy(() =>
  import('./pages/UpdateBalancesPage').then((module) => ({ default: module.UpdateBalancesPage })),
);

const SELECTED_HOUSEHOLD_STORAGE_KEY = 'netwise.selectedHouseholdId';
const THEME_STORAGE_KEY = 'netwise.theme';

function storedSelection(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? '';
  } catch {
    return '';
  }
}

function persistSelection(key: string, value: string): void {
  try {
    if (value) {
      window.localStorage.setItem(key, value);
    } else {
      window.localStorage.removeItem(key);
    }
  } catch {
    // Selection persistence is optional when storage is unavailable.
  }
}

function storedThemePreference(): ThemePreference {
  const storedTheme = storedSelection(THEME_STORAGE_KEY);
  return storedTheme === 'light' || storedTheme === 'dark' || storedTheme === 'system'
    ? storedTheme
    : 'system';
}

function systemPrefersDarkTheme(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function optionalString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value ? value : undefined;
}

function requiredString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

function exportFilename(name: string): string {
  const safeName = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '') || 'household';
  return `netwise-${safeName}-export-${today()}.json`;
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

function WorkspaceView({
  view,
  householdName,
  children,
}: {
  view: AppView;
  householdName: string;
  children: ReactNode;
}) {
  return (
    <>
      <ViewHeading activeView={view} householdName={householdName} />
      <Suspense fallback={<div className="card" role="status">Loading page…</div>}>
        {children}
      </Suspense>
    </>
  );
}

function App({
  authenticatedUser,
  onLogout,
}: {
  authenticatedUser: User;
  onLogout: () => Promise<void>;
}) {
  const householdRequestId = useRef(0);
  const dashboardRequestId = useRef(0);
  const [themePreference, setThemePreference] = useState<ThemePreference>(storedThemePreference);
  const [systemDarkTheme, setSystemDarkTheme] = useState<boolean>(systemPrefersDarkTheme);
  const [users, setUsers] = useState<User[]>([authenticatedUser]);
  const [selectedUserId] = useState<string>(authenticatedUser.id);
  const [households, setHouseholds] = useState<Household[]>([]);
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string>(() =>
    storedSelection(SELECTED_HOUSEHOLD_STORAGE_KEY),
  );
  const [householdMembers, setHouseholdMembers] = useState<HouseholdMembership[]>([]);
  const [projectionTransfers, setProjectionTransfers] = useState<ProjectionTransfer[]>([]);
  const [projection, setProjection] = useState<NetWorthProjection | null>(null);
  const [projectionRunning, setProjectionRunning] = useState<boolean>(false);
  const [projectionSettings, setProjectionSettings] = useState<ProjectionSettings | null>(null);
  const [fintrackImportResult, setFintrackImportResult] = useState<FintrackImportResult | null>(null);
  const [fintrackDryRun, setFintrackDryRun] = useState<boolean>(true);
  const [adminToolsEnabled, setAdminToolsEnabled] = useState<boolean>(false);
  const [fintrackImportEnabled, setFintrackImportEnabled] = useState<boolean>(false);
  const [showInterpolatedHistory, setShowInterpolatedHistory] = useState<boolean>(false);
  const [showProjectionOnTrajectory, setShowProjectionOnTrajectory] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [dashboardLoading, setDashboardLoading] = useState<boolean>(false);
  const [loadedHouseholdId, setLoadedHouseholdId] = useState<string>('');
  const [householdsLoading, setHouseholdsLoading] = useState<boolean>(false);
  const queryClient = useQueryClient();
  const accountsQuery = useAccounts(selectedHouseholdId);
  const financialSummary = useHouseholdFinancialSummary(
    selectedHouseholdId,
    showInterpolatedHistory,
  );
  const accounts = accountsQuery.data ?? [];
  const netWorth = financialSummary.netWorth.data ?? null;
  const history = financialSummary.history.data ?? null;
  const breakdownHistory = financialSummary.breakdownHistory.data ?? null;
  const queryDataLoading = Boolean(selectedHouseholdId) && [
    accountsQuery,
    financialSummary.netWorth,
    financialSummary.history,
    financialSummary.breakdownHistory,
  ].some((query) => query.isPending);

  const queryDataError = [
    accountsQuery,
    financialSummary.netWorth,
    financialSummary.history,
    financialSummary.breakdownHistory,
  ].find((query) => query.error)?.error;

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? authenticatedUser,
    [authenticatedUser, users, selectedUserId],
  );

  const selectedHousehold = useMemo(
    () => households.find((household) => household.id === selectedHouseholdId),
    [households, selectedHouseholdId],
  );

  const currentHouseholdRole = useMemo(
    () => householdMembers.find((membership) => membership.user_id === authenticatedUser.id)?.role ?? 'viewer',
    [authenticatedUser.id, householdMembers],
  );

  const accountNameById = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.name])),
    [accounts],
  );

  const latestBalanceByAccountId = useMemo(
    () => new Map((netWorth?.accounts ?? []).map((account) => [account.account_id, account.balance])),
    [netWorth],
  );

  const assetAccounts = accounts.filter((account) => account.account_kind === 'asset');

  const propertyAccounts = accounts.filter(
    (account) => account.account_kind === 'asset' && account.category === 'real_estate',
  );

  const availableUsersForMembership = users.filter(
    (user) => !householdMembers.some((membership) => membership.user_id === user.id),
  );

  async function refreshUsers() {
    const userList = await listUsers();
    setUsers(userList);
  }

  async function refreshHouseholds(userId: string) {
    const requestId = ++householdRequestId.current;
    setHouseholdsLoading(true);
    try {
      const householdList = await listHouseholds(userId);
      if (requestId !== householdRequestId.current) return;
      setHouseholds(householdList);
      setSelectedHouseholdId((currentHouseholdId) => {
        if (householdList.length === 0) return '';
        return householdList.some((household) => household.id === currentHouseholdId)
          ? currentHouseholdId
          : householdList[0].id;
      });
    } finally {
      if (requestId === householdRequestId.current) setHouseholdsLoading(false);
    }
  }

  async function refreshDashboard(householdId: string, refreshQueryData = true) {
    const requestId = ++dashboardRequestId.current;
    setDashboardLoading(true);
    try {
      const queryRefresh = refreshQueryData
        ? queryClient.invalidateQueries({ queryKey: householdQueryKeys.all(householdId) })
        : Promise.resolve();
      const [
        projectionTransferList,
        memberList,
        projectionSettingsResult,
      ] = await Promise.all([
        listProjectionTransfers(householdId),
        listHouseholdMembers(householdId),
        getProjectionSettings(householdId),
      ]);
      await queryRefresh;
      if (requestId !== dashboardRequestId.current) return;

      setHouseholdMembers(memberList);
      setProjectionTransfers(projectionTransferList);
      setProjectionSettings(projectionSettingsResult);
      setLoadedHouseholdId(householdId);
    } finally {
      if (requestId === dashboardRequestId.current) setDashboardLoading(false);
    }
  }

  async function handleLogout() {
    queryClient.clear();
    await onLogout();
  }

  useEffect(() => {
    if (queryDataError) setError(String(queryDataError));
  }, [queryDataError]);

  useEffect(() => {
    const colorScheme = window.matchMedia('(prefers-color-scheme: dark)');
    const handleColorSchemeChange = (event: MediaQueryListEvent) => setSystemDarkTheme(event.matches);
    colorScheme.addEventListener('change', handleColorSchemeChange);
    return () => colorScheme.removeEventListener('change', handleColorSchemeChange);
  }, []);

  useLayoutEffect(() => {
    const resolvedTheme = themePreference === 'system'
      ? (systemDarkTheme ? 'dark' : 'light')
      : themePreference;
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme;
    persistSelection(THEME_STORAGE_KEY, themePreference);
  }, [systemDarkTheme, themePreference]);

  useEffect(() => {
    persistSelection(SELECTED_HOUSEHOLD_STORAGE_KEY, selectedHouseholdId);
  }, [selectedHouseholdId]);

  useEffect(() => {
    Promise.all([refreshUsers(), getCapabilities()])
      .then(([, capabilities]) => {
        setAdminToolsEnabled(capabilities.admin_tools_enabled);
        setFintrackImportEnabled(capabilities.fintrack_import_enabled);
      })
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedUserId) {
      householdRequestId.current += 1;
      setHouseholds([]);
      setSelectedHouseholdId('');
      setHouseholdsLoading(false);
      return;
    }
    setHouseholds([]);
    refreshHouseholds(selectedUserId).catch((err: unknown) => setError(String(err)));
  }, [selectedUserId]);

  useEffect(() => {
    if (!selectedHouseholdId) return;
    setProjection(null);
    setProjectionSettings(null);
    setFintrackImportResult(null);
  }, [selectedHouseholdId]);

  useEffect(() => {
    if (!selectedHouseholdId) {
      dashboardRequestId.current += 1;
      setLoadedHouseholdId('');
      setDashboardLoading(false);
      return;
    }
    refreshDashboard(selectedHouseholdId, false).catch((err: unknown) => setError(String(err)));
  }, [selectedHouseholdId]);

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    setError('');
    const form = new FormData(target);
    const displayName = String(form.get('display_name') ?? '').trim();
    const email = String(form.get('email') ?? '').trim();
    if (!displayName) return;
    try {
      const user = await createUser({ display_name: displayName, email: email || undefined });
      target.reset();
      setUsers((current) => [...current.filter((item) => item.id !== user.id), user]);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateHousehold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    setError('');
    const form = new FormData(target);
    const name = String(form.get('name') ?? '').trim();
    if (!name || !selectedUserId) return;
    try {
      const household = await createHousehold(name, selectedUserId);
      target.reset();
      await refreshHouseholds(selectedUserId);
      setSelectedHouseholdId(household.id);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleAddHouseholdMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    const target = event.currentTarget;
    const form = new FormData(target);
    const userId = requiredString(form, 'user_id');
    const role = requiredString(form, 'role');
    setError('');
    try {
      await addHouseholdMember(selectedHouseholdId, { user_id: userId, role });
      target.reset();
      setHouseholdMembers(await listHouseholdMembers(selectedHouseholdId));
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleRemoveHouseholdMember(userId: string) {
    if (!selectedHouseholdId) return;
    setError('');
    try {
      await removeHouseholdMember(selectedHouseholdId, userId);
      setHouseholdMembers(await listHouseholdMembers(selectedHouseholdId));
      if (userId === selectedUserId) {
        await refreshHouseholds(selectedUserId);
      }
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateProjectionTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createProjectionTransfer({
        household_id: selectedHouseholdId,
        name: requiredString(form, 'transfer_name'),
        from_account_id: requiredString(form, 'transfer_from_account_id'),
        to_account_id: requiredString(form, 'transfer_to_account_id'),
        annual_amount: requiredString(form, 'transfer_annual_amount'),
        start_date: requiredString(form, 'transfer_start_date'),
        end_date: optionalString(form, 'transfer_end_date'),
        growth_rate: optionalString(form, 'transfer_growth_rate'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleDeleteProjectionTransfer(projectionTransfer: ProjectionTransfer) {
    if (!selectedHouseholdId) return;
    if (!window.confirm(`Delete recurring transfer ${projectionTransfer.name}?`)) return;
    setError('');
    try {
      await deleteProjectionTransfer(projectionTransfer.id);
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleGetProjection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    setError('');
    setProjectionRunning(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await getNetWorthProjection(
        selectedHouseholdId,
        Number(requiredString(form, 'projection_start_year')),
        Number(requiredString(form, 'projection_end_year')),
        {
          annualSpending: optionalString(form, 'projection_annual_spending'),
          spendingInflationRate: optionalString(form, 'projection_spending_inflation_rate'),
          spendingAccountId: optionalString(form, 'projection_spending_account_id'),
          taxAccountId: optionalString(form, 'projection_tax_account_id'),
          interval: requiredString(form, 'projection_interval') as 'annual' | 'quarterly' | 'monthly',
        },
      );
      setProjection(result);
    } catch (err: unknown) {
      setProjection(null);
      setError(String(err));
    } finally {
      setProjectionRunning(false);
    }
  }

  async function handleSpendingModeChange(mode: 'manual' | 'itemized') {
    if (!selectedHouseholdId) return;
    setError('');
    try {
      const result = await upsertProjectionSettings(selectedHouseholdId, {
        annual_spending: projectionSettings?.annual_spending ?? undefined,
        spending_mode: mode,
        spending_inflation_rate: projectionSettings?.spending_inflation_rate ?? undefined,
        retirement_date: projectionSettings?.retirement_date ?? undefined,
        retirement_annual_spending: projectionSettings?.retirement_annual_spending ?? undefined,
        spending_account_id: projectionSettings?.spending_account_id ?? undefined,
        tax_account_id: projectionSettings?.tax_account_id ?? undefined,
      });
      setProjectionSettings(result);
      setProjection(null);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleSaveProjectionSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      const result = await upsertProjectionSettings(selectedHouseholdId, {
        annual_spending: optionalString(form, 'settings_annual_spending'),
        spending_mode: requiredString(form, 'settings_spending_mode') as 'manual' | 'itemized',
        spending_inflation_rate: optionalString(form, 'settings_spending_inflation_rate'),
        retirement_date: optionalString(form, 'settings_retirement_date'),
        retirement_annual_spending: optionalString(
          form,
          'settings_retirement_annual_spending',
        ),
        spending_account_id: optionalString(form, 'settings_spending_account_id'),
        tax_account_id: optionalString(form, 'settings_tax_account_id'),
      });
      setProjectionSettings(result);
      setProjection(null);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleDownloadHouseholdExport() {
    if (!selectedHouseholdId || !selectedHousehold) return;
    setError('');
    try {
      const result = await exportHousehold(selectedHouseholdId);
      downloadJson(exportFilename(selectedHousehold.name), result);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleImportFintrack(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    const target = event.currentTarget;
    const form = new FormData(target);
    const dryRun = form.get('dry_run') === 'on';
    if (!dryRun) {
      const confirmed = window.confirm(
        `Import FinTrack data into ${selectedHousehold?.name ?? 'the selected household'}? This will write accounts, snapshots, and events to the database.`,
      );
      if (!confirmed) return;
    }
    setError('');
    setFintrackImportResult(null);
    try {
      const result = await importFintrack({
        household_id: selectedHouseholdId,
        data_dir: requiredString(form, 'data_dir'),
        currency: optionalString(form, 'currency') || 'USD',
        dry_run: dryRun,
      });
      setFintrackImportResult(result);
      if (!result.dry_run) {
        await refreshDashboard(selectedHouseholdId);
      }
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  return (
    <main className="app-shell">
      <AppHeader
        currentUser={authenticatedUser}
        onLogout={handleLogout}
        households={households}
        selectedHousehold={selectedHousehold}
        selectedHouseholdId={selectedHouseholdId}
        onSelectHousehold={setSelectedHouseholdId}
        themePreference={themePreference}
        onThemePreferenceChange={setThemePreference}
      />

      {selectedHousehold && <AppNavigation />}

      {error && <div className="error" role="alert">{error}</div>}
      {selectedHousehold && currentHouseholdRole === 'viewer' && loadedHouseholdId === selectedHousehold.id && (
        <div className="card" role="status">You have read-only access to this household.</div>
      )}
      {loading && <div className="card">Loading…</div>}

      {!loading && users.length === 0 && (
        <section className="card narrow">
          <h2>Create your user</h2>
          <p className="muted">Users own or join households. Authentication can be added later.</p>
          <form onSubmit={handleCreateUser} className="form-grid compact-form">
            <input name="display_name" placeholder="Your name" required />
            <input name="email" type="email" placeholder="Email (optional)" />
            <button type="submit">Create user</button>
          </form>
        </section>
      )}

      {!loading && !householdsLoading && users.length > 0 && households.length === 0 && (
        <section className="card narrow">
          <h2>Create your household</h2>
          <p className="muted">This household will be owned by {selectedUser?.display_name ?? 'the selected user'}.</p>
          <form onSubmit={handleCreateHousehold} className="form-row">
            <input name="name" placeholder="Home" required />
            <button type="submit">Create</button>
          </form>
        </section>
      )}

      {selectedHousehold && (dashboardLoading || queryDataLoading) && (
        loadedHouseholdId !== selectedHousehold.id || queryDataLoading
      ) && (
        <div className="card" role="status">Loading {selectedHousehold.name}…</div>
      )}

      {selectedHousehold && loadedHouseholdId === selectedHousehold.id && !queryDataLoading && (
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route
            path="/overview"
            element={
              <WorkspaceView view="overview" householdName={selectedHousehold.name}>
                <OverviewPage
                  netWorth={netWorth}
                  history={history}
                  projection={projection}
                  breakdownHistory={breakdownHistory}
                  showInterpolatedHistory={showInterpolatedHistory}
                  onShowInterpolatedHistory={setShowInterpolatedHistory}
                  showProjectionOnTrajectory={showProjectionOnTrajectory}
                  onShowProjectionOnTrajectory={setShowProjectionOnTrajectory}
                />
              </WorkspaceView>
            }
          />
          <Route
            path="/update"
            element={
              <WorkspaceView view="update" householdName={selectedHousehold.name}>
                <UpdateBalancesPage
                  householdId={selectedHouseholdId}
                  accounts={accounts}
                  latestBalanceByAccountId={latestBalanceByAccountId}
                  defaultDate={today()}
                />
              </WorkspaceView>
            }
          />
          <Route
            path="/plan"
            element={
              <WorkspaceView view="plan" householdName={selectedHousehold.name}>
                <PlanningPage
                  householdId={selectedHouseholdId}
                  defaultDate={today()}
                  accounts={accounts}
                  assetAccounts={assetAccounts}
                  propertyAccounts={propertyAccounts}
                  accountNameById={accountNameById}
                  projectionSettings={projectionSettings}
                  onSpendingModeChange={handleSpendingModeChange}
                  onSaveProjectionSettings={handleSaveProjectionSettings}
                  onGetProjection={handleGetProjection}
                  projectionRunning={projectionRunning}
                  projectionTransfers={projectionTransfers}
                  projection={projection}
                  onInvalidateProjection={() => setProjection(null)}
                  onCreateProjectionTransfer={handleCreateProjectionTransfer}
                  onDeleteProjectionTransfer={handleDeleteProjectionTransfer}
                />
              </WorkspaceView>
            }
          />
          <Route
            path="/assets"
            element={
              <WorkspaceView view="assets" householdName={selectedHousehold.name}>
                <AssetsPage
                  householdId={selectedHouseholdId}
                  defaultDate={today()}
                  accounts={accounts}
                  assetAccounts={assetAccounts}
                  propertyAccounts={propertyAccounts}
                  accountNameById={accountNameById}
                  latestBalanceByAccountId={latestBalanceByAccountId}
                />
              </WorkspaceView>
            }
          />
          <Route
            path="/settings"
            element={
              <WorkspaceView view="settings" householdName={selectedHousehold.name}>
                <HouseholdSettingsPage
                  household={selectedHousehold}
                  members={householdMembers}
                  availableUsers={availableUsersForMembership}
                  adminToolsEnabled={adminToolsEnabled}
                  fintrackImportEnabled={fintrackImportEnabled}
                  currentRole={currentHouseholdRole}
                  onDownloadExport={handleDownloadHouseholdExport}
                  onCreateHousehold={handleCreateHousehold}
                  onCreateUser={handleCreateUser}
                  onRemoveMember={handleRemoveHouseholdMember}
                  onAddMember={handleAddHouseholdMember}
                  fintrackDryRun={fintrackDryRun}
                  onFintrackDryRun={setFintrackDryRun}
                  onImportFintrack={handleImportFintrack}
                  fintrackImportResult={fintrackImportResult}
                />
              </WorkspaceView>
            }
          />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      )}
    </main>
  );
}

export default App;
