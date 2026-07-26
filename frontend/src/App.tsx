import { useQueryClient } from '@tanstack/react-query';
import {
  FormEvent,
  Suspense,
  lazy,
  type ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Navigate, Route, Routes } from 'react-router';
import {
  Account,
  Household,
  NetWorthProjection,
  User,
  createHousehold,
  getNetWorthProjection,
  listHouseholds,
} from './api';
import {
  AppHeader,
  AppNavigation,
  ViewHeading,
  type AppView,
  type ThemePreference,
} from './components/AppShell';
import {
  useAccounts,
  useHouseholdFinancialSummary,
  useHouseholdMembers,
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
  const [themePreference, setThemePreference] = useState<ThemePreference>(storedThemePreference);
  const [systemDarkTheme, setSystemDarkTheme] = useState<boolean>(systemPrefersDarkTheme);
  const selectedUserId = authenticatedUser.id;
  const [households, setHouseholds] = useState<Household[]>([]);
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string>(() =>
    storedSelection(SELECTED_HOUSEHOLD_STORAGE_KEY),
  );
  const [projection, setProjection] = useState<NetWorthProjection | null>(null);
  const [projectionRunning, setProjectionRunning] = useState<boolean>(false);
  const invalidateProjection = useCallback(() => setProjection(null), []);
  const [showInterpolatedHistory, setShowInterpolatedHistory] = useState<boolean>(false);
  const [showProjectionOnTrajectory, setShowProjectionOnTrajectory] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [householdsLoading, setHouseholdsLoading] = useState<boolean>(true);
  const queryClient = useQueryClient();
  const accountsQuery = useAccounts(selectedHouseholdId);
  const membersQuery = useHouseholdMembers(selectedHouseholdId);
  const financialSummary = useHouseholdFinancialSummary(
    selectedHouseholdId,
    showInterpolatedHistory,
  );
  const accounts = accountsQuery.data ?? [];
  const householdMembers = membersQuery.data ?? [];
  const netWorth = financialSummary.netWorth.data ?? null;
  const history = financialSummary.history.data ?? null;
  const breakdownHistory = financialSummary.breakdownHistory.data ?? null;
  const queryDataLoading = Boolean(selectedHouseholdId) && [
    accountsQuery,
    membersQuery,
    financialSummary.netWorth,
    financialSummary.history,
    financialSummary.breakdownHistory,
  ].some((query) => query.isPending);

  const queryDataError = [
    accountsQuery,
    membersQuery,
    financialSummary.netWorth,
    financialSummary.history,
    financialSummary.breakdownHistory,
  ].find((query) => query.error)?.error;

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
  }, [selectedHouseholdId]);

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
          scenarioId: requiredString(form, 'scenario_id'),
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
      {selectedHousehold && currentHouseholdRole === 'viewer' && !membersQuery.isPending && (
        <div className="card" role="status">You have read-only access to this household.</div>
      )}

      {!householdsLoading && households.length === 0 && (
        <section className="card narrow">
          <h2>Create your household</h2>
          <p className="muted">This household will be owned by {authenticatedUser.display_name}.</p>
          <form onSubmit={handleCreateHousehold} className="form-row">
            <input name="name" placeholder="Home" required />
            <button type="submit">Create</button>
          </form>
        </section>
      )}

      {selectedHousehold && queryDataLoading && (
        <div className="card" role="status">Loading {selectedHousehold.name}…</div>
      )}

      {selectedHousehold && !queryDataLoading && (
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
                  canEdit={currentHouseholdRole !== 'viewer'}
                  onGetProjection={handleGetProjection}
                  projectionRunning={projectionRunning}
                  projection={projection}
                  onInvalidateProjection={invalidateProjection}
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
                  authenticatedUserId={authenticatedUser.id}
                  onCreateHousehold={handleCreateHousehold}
                  onCurrentUserRemoved={() => refreshHouseholds(selectedUserId)}
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
