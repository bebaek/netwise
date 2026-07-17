import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Account,
  AccountEvent,
  AnnualExpenseEstimate,
  AnnualTaxRecord,
  FintrackImportResult,
  Household,
  HouseholdMembership,
  HouseholdSnapshot,
  IncomeSource,
  MortgageProfile,
  NetWorth,
  NetWorthBreakdownHistory,
  NetWorthHistory,
  NetWorthProjection,
  RealEstateProperty,
  User,
  addHouseholdMember,
  createAccount,
  createAccountEvent,
  createAnnualTaxRecord,
  createHousehold,
  createIncomeSource,
  createMortgageProfile,
  createRealEstateProperty,
  createSnapshot,
  createSnapshotBatch,
  createUser,
  deleteSnapshot,
  exportHousehold,
  getAnnualExpenseEstimate,
  getCapabilities,
  getHistoricalTrend,
  getNetWorth,
  getNetWorthBreakdownHistory,
  getNetWorthProjection,
  importFintrack,
  listAccounts,
  listAccountEvents,
  listAnnualTaxRecords,
  listHouseholds,
  listHouseholdMembers,
  listHouseholdSnapshots,
  listIncomeSources,
  listMortgageProfiles,
  listRealEstateProperties,
  listUsers,
  removeHouseholdMember,
  updateSnapshot,
} from './api';
import './styles.css';

function formatMoney(value: string | null | undefined): string {
  if (value == null) return '—';
  return Number(value).toLocaleString(undefined, { style: 'currency', currency: 'USD' });
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

function categoryBalance(
  categories: Array<{ category: string; balance: string }>,
  category: string,
): string | null {
  return categories.find((item) => item.category === category)?.balance ?? null;
}

type TrajectoryProjectionPoint = Pick<NetWorthProjection['points'][number], 'as_of_date' | 'net_worth'>;

function dateMs(value: string): number {
  return new Date(`${value}T00:00:00`).getTime();
}

function HistoryChart({
  points,
  projectionPoints = [],
}: {
  points: NetWorthHistory['points'];
  projectionPoints?: TrajectoryProjectionPoint[];
}) {
  const sortedHistory = [...points].sort((left, right) => left.as_of_date.localeCompare(right.as_of_date));
  const lastHistoryPoint = sortedHistory[sortedHistory.length - 1];
  const visibleProjectionPoints = [...projectionPoints]
    .filter((point) => !lastHistoryPoint || point.as_of_date > lastHistoryPoint.as_of_date)
    .sort((left, right) => left.as_of_date.localeCompare(right.as_of_date));
  const chartPoints = [...sortedHistory, ...visibleProjectionPoints];
  if (chartPoints.length < 2) return null;

  const values = chartPoints.map((point) => Number(point.net_worth));
  const dates = chartPoints.map((point) => dateMs(point.as_of_date));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const minDate = Math.min(...dates);
  const maxDate = Math.max(...dates);
  const valueRange = maxValue - minValue || 1;
  const dateRange = maxDate - minDate || 1;
  const width = 720;
  const height = 240;
  const padding = 28;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const xForDate = (value: string) => padding + ((dateMs(value) - minDate) / dateRange) * plotWidth;
  const yForValue = (value: number) => padding + plotHeight - ((value - minValue) / valueRange) * plotHeight;
  const polylineFor = (items: Array<{ as_of_date: string; net_worth: string }>) =>
    items.map((point) => `${xForDate(point.as_of_date)},${yForValue(Number(point.net_worth))}`).join(' ');
  const historyPolyline = polylineFor(sortedHistory);
  const projectionPolyline = lastHistoryPoint
    ? polylineFor([lastHistoryPoint, ...visibleProjectionPoints])
    : polylineFor(visibleProjectionPoints);

  return (
    <div className="trend-chart" aria-label="Financial trajectory chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <title>Financial trajectory</title>
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="axis" />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} className="axis" />
        <polyline points={historyPolyline} className="trend-line history" />
        {visibleProjectionPoints.length > 0 && <polyline points={projectionPolyline} className="trend-line projection" />}
        {sortedHistory.map((point) => (
          <circle
            key={`${point.as_of_date}-${point.estimated ? 'estimate' : 'snapshot'}`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={point.estimated ? 3 : 5}
            className={point.estimated ? 'trend-dot estimate' : 'trend-dot snapshot'}
          />
        ))}
        {visibleProjectionPoints.map((point) => (
          <circle
            key={`${point.as_of_date}-projection`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={4}
            className="trend-dot projection"
          />
        ))}
      </svg>
      <div className="chart-labels">
        <span>{chartPoints[0]?.as_of_date}</span>
        <span>{chartPoints[chartPoints.length - 1]?.as_of_date}</span>
      </div>
      <div className="chart-legend">
        <span><i className="legend-dot snapshot" />Snapshot</span>
        <span><i className="legend-dot estimate" />Estimate</span>
        {visibleProjectionPoints.length > 0 && <span><i className="legend-dot projection" />Projection</span>}
      </div>
    </div>
  );
}

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [households, setHouseholds] = useState<Household[]>([]);
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string>('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountEvents, setAccountEvents] = useState<AccountEvent[]>([]);
  const [householdSnapshots, setHouseholdSnapshots] = useState<HouseholdSnapshot[]>([]);
  const [householdMembers, setHouseholdMembers] = useState<HouseholdMembership[]>([]);
  const [snapshotAccountFilter, setSnapshotAccountFilter] = useState<string>('');
  const [snapshotEditDraft, setSnapshotEditDraft] = useState<{
    id: string;
    as_of_date: string;
    balance: string;
  } | null>(null);
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [history, setHistory] = useState<NetWorthHistory | null>(null);
  const [breakdownHistory, setBreakdownHistory] = useState<NetWorthBreakdownHistory | null>(null);
  const [properties, setProperties] = useState<RealEstateProperty[]>([]);
  const [mortgages, setMortgages] = useState<MortgageProfile[]>([]);
  const [incomeSources, setIncomeSources] = useState<IncomeSource[]>([]);
  const [taxRecords, setTaxRecords] = useState<AnnualTaxRecord[]>([]);
  const [expenseEstimate, setExpenseEstimate] = useState<AnnualExpenseEstimate | null>(null);
  const [projection, setProjection] = useState<NetWorthProjection | null>(null);
  const [fintrackImportResult, setFintrackImportResult] = useState<FintrackImportResult | null>(null);
  const [fintrackDryRun, setFintrackDryRun] = useState<boolean>(true);
  const [adminToolsEnabled, setAdminToolsEnabled] = useState<boolean>(false);
  const [snapshotBatchMessage, setSnapshotBatchMessage] = useState<string>('');
  const [showInterpolatedHistory, setShowInterpolatedHistory] = useState<boolean>(false);
  const [showProjectionOnTrajectory, setShowProjectionOnTrajectory] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId),
    [users, selectedUserId],
  );

  const selectedHousehold = useMemo(
    () => households.find((household) => household.id === selectedHouseholdId),
    [households, selectedHouseholdId],
  );

  const accountNameById = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.name])),
    [accounts],
  );

  const latestBalanceByAccountId = useMemo(
    () => new Map((netWorth?.accounts ?? []).map((account) => [account.account_id, account.balance])),
    [netWorth],
  );

  const breakdownCategories = useMemo(() => {
    const assetCategories = new Set<string>();
    const liabilityCategories = new Set<string>();
    for (const point of breakdownHistory?.points ?? []) {
      point.asset_categories.forEach((item) => assetCategories.add(item.category));
      point.liability_categories.forEach((item) => liabilityCategories.add(item.category));
    }
    return {
      assetCategories: [...assetCategories].sort(),
      liabilityCategories: [...liabilityCategories].sort(),
    };
  }, [breakdownHistory]);

  const propertyAccounts = accounts.filter(
    (account) => account.account_kind === 'asset' && account.category === 'real_estate',
  );

  const availableUsersForMembership = users.filter(
    (user) => !householdMembers.some((membership) => membership.user_id === user.id),
  );

  async function refreshUsers() {
    const userList = await listUsers();
    setUsers(userList);
    if (!selectedUserId && userList.length > 0) {
      setSelectedUserId(userList[0].id);
    }
  }

  async function refreshHouseholds(userId: string) {
    const householdList = await listHouseholds(userId);
    setHouseholds(householdList);
    if (householdList.length === 0) {
      setSelectedHouseholdId('');
      return;
    }
    if (!householdList.some((household) => household.id === selectedHouseholdId)) {
      setSelectedHouseholdId(householdList[0].id);
    }
  }

  async function refreshDashboard(householdId: string) {
    const [
      accountList,
      netWorthResult,
      historyResult,
      propertyList,
      mortgageList,
      incomeSourceList,
      taxRecordList,
      snapshotList,
      breakdownResult,
      memberList,
    ] = await Promise.all([
      listAccounts(householdId),
      getNetWorth(householdId),
      getHistoricalTrend(householdId, showInterpolatedHistory),
      listRealEstateProperties(householdId),
      listMortgageProfiles(householdId),
      listIncomeSources(householdId),
      listAnnualTaxRecords(householdId),
      listHouseholdSnapshots(householdId, snapshotAccountFilter || undefined),
      getNetWorthBreakdownHistory(householdId),
      listHouseholdMembers(householdId),
    ]);
    const accountEventList = (await Promise.all(accountList.map((account) => listAccountEvents(account.id))))
      .flat()
      .sort((left, right) => right.event_date.localeCompare(left.event_date));
    setAccounts(accountList);
    setAccountEvents(accountEventList);
    setHouseholdSnapshots(snapshotList);
    setHouseholdMembers(memberList);
    setNetWorth(netWorthResult);
    setHistory(historyResult);
    setBreakdownHistory(breakdownResult);
    setProperties(propertyList);
    setMortgages(mortgageList);
    setIncomeSources(incomeSourceList);
    setTaxRecords(taxRecordList);
  }

  useEffect(() => {
    Promise.all([refreshUsers(), getCapabilities()])
      .then(([, capabilities]) => setAdminToolsEnabled(capabilities.admin_tools_enabled))
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedUserId) {
      setHouseholds([]);
      setSelectedHouseholdId('');
      return;
    }
    refreshHouseholds(selectedUserId).catch((err: unknown) => setError(String(err)));
  }, [selectedUserId]);

  useEffect(() => {
    if (!selectedHouseholdId) return;
    setExpenseEstimate(null);
    setProjection(null);
    setFintrackImportResult(null);
    setSnapshotBatchMessage('');
    setSnapshotEditDraft(null);
  }, [selectedHouseholdId]);

  useEffect(() => {
    if (!selectedHouseholdId) return;
    refreshDashboard(selectedHouseholdId).catch((err: unknown) => setError(String(err)));
  }, [selectedHouseholdId, showInterpolatedHistory, snapshotAccountFilter]);

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
      await refreshUsers();
      setSelectedUserId(user.id);
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

  async function handleCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createAccount({
        household_id: selectedHouseholdId,
        name: String(form.get('name') ?? ''),
        account_kind: String(form.get('account_kind')) as 'asset' | 'liability',
        category: String(form.get('category') ?? ''),
        liquidity_class: String(form.get('liquidity_class') ?? ''),
        expected_annual_yield: optionalString(form, 'expected_annual_yield'),
        currency: 'USD',
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createSnapshot(String(form.get('account_id')), {
        as_of_date: String(form.get('as_of_date')),
        balance: String(form.get('balance')),
        currency: 'USD',
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateSnapshotBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
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
      const result = await createSnapshotBatch(selectedHouseholdId, {
        as_of_date: requiredString(form, 'as_of_date'),
        currency: 'USD',
        snapshots,
      });
      target.reset();
      setSnapshotBatchMessage(
        `Saved ${result.created_count} new and ${result.updated_count} updated snapshot${result.snapshots.length === 1 ? '' : 's'}.`,
      );
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleUpdateSnapshot(snapshot: HouseholdSnapshot) {
    if (!selectedHouseholdId || snapshotEditDraft?.id !== snapshot.id) return;
    setError('');
    try {
      await updateSnapshot(snapshot.account_id, snapshot.id, {
        as_of_date: snapshotEditDraft.as_of_date,
        balance: snapshotEditDraft.balance,
        currency: snapshot.currency,
      });
      setSnapshotEditDraft(null);
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleDeleteSnapshot(snapshot: HouseholdSnapshot) {
    if (!selectedHouseholdId) return;
    const confirmed = window.confirm(
      `Delete ${snapshot.account_name} snapshot from ${snapshot.as_of_date}?`,
    );
    if (!confirmed) return;
    setError('');
    try {
      await deleteSnapshot(snapshot.account_id, snapshot.id);
      if (snapshotEditDraft?.id === snapshot.id) setSnapshotEditDraft(null);
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateAccountEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createAccountEvent(requiredString(form, 'account_id'), {
        event_date: requiredString(form, 'event_date'),
        amount: requiredString(form, 'amount'),
        currency: 'USD',
        event_type: requiredString(form, 'event_type'),
        description: optionalString(form, 'description'),
        projection_behavior: requiredString(form, 'projection_behavior'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      const propertyName = requiredString(form, 'property_name');
      const currentValue = optionalString(form, 'current_value');
      const valuationDate = optionalString(form, 'valuation_date') ?? today();
      const propertyAccount = await createAccount({
        household_id: selectedHouseholdId,
        name: propertyName,
        account_kind: 'asset',
        category: 'real_estate',
        liquidity_class: 'illiquid',
        expected_annual_yield: optionalString(form, 'expected_appreciation_rate'),
        currency: 'USD',
      });
      await createRealEstateProperty({
        account_id: propertyAccount.id,
        property_type: optionalString(form, 'property_type') ?? 'residence',
        purchase_date: optionalString(form, 'purchase_date'),
        purchase_price: optionalString(form, 'purchase_price'),
        down_payment: optionalString(form, 'down_payment'),
        expected_appreciation_rate: optionalString(form, 'expected_appreciation_rate'),
        property_tax_annual: optionalString(form, 'property_tax_annual'),
        insurance_annual: optionalString(form, 'insurance_annual'),
        maintenance_rate: optionalString(form, 'maintenance_rate'),
        hoa_monthly: optionalString(form, 'hoa_monthly'),
      });
      if (currentValue) {
        await createSnapshot(propertyAccount.id, {
          as_of_date: valuationDate,
          balance: currentValue,
          currency: 'USD',
        });
      }
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateMortgage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      const originalPrincipal = requiredString(form, 'original_principal');
      const startDate = requiredString(form, 'start_date');
      const currentBalance = optionalString(form, 'current_balance') ?? originalPrincipal;
      const balanceDate = optionalString(form, 'balance_date') ?? startDate;
      const propertyAccountId = optionalString(form, 'property_account_id');
      const liabilityAccount = await createAccount({
        household_id: selectedHouseholdId,
        name: requiredString(form, 'mortgage_name'),
        account_kind: 'liability',
        category: 'mortgage',
        liquidity_class: 'debt',
        expected_annual_yield: '0.000000',
        currency: 'USD',
      });
      await createMortgageProfile({
        liability_account_id: liabilityAccount.id,
        property_account_id: propertyAccountId,
        original_principal: originalPrincipal,
        interest_rate: requiredString(form, 'interest_rate'),
        term_months: Number(requiredString(form, 'term_months')),
        start_date: startDate,
        monthly_payment: optionalString(form, 'monthly_payment'),
        rate_type: optionalString(form, 'rate_type') ?? 'fixed',
      });
      if (currentBalance) {
        await createSnapshot(liabilityAccount.id, {
          as_of_date: balanceDate,
          balance: currentBalance,
          currency: 'USD',
        });
      }
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateIncomeSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createIncomeSource({
        household_id: selectedHouseholdId,
        name: requiredString(form, 'income_name'),
        income_type: optionalString(form, 'income_type') ?? 'other',
        amount: requiredString(form, 'amount'),
        currency: 'USD',
        frequency: requiredString(form, 'frequency'),
        start_date: requiredString(form, 'start_date'),
        end_date: optionalString(form, 'end_date'),
        growth_rate: optionalString(form, 'growth_rate'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateTaxRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createAnnualTaxRecord({
        household_id: selectedHouseholdId,
        tax_year: Number(requiredString(form, 'tax_year')),
        gross_income: optionalString(form, 'gross_income'),
        total_taxes_paid: requiredString(form, 'total_taxes_paid'),
        refund_or_amount_due: optionalString(form, 'refund_or_amount_due'),
        notes: optionalString(form, 'notes'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleGetExpenseEstimate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      const result = await getAnnualExpenseEstimate(
        selectedHouseholdId,
        Number(requiredString(form, 'tax_year')),
      );
      setExpenseEstimate(result);
    } catch (err: unknown) {
      setExpenseEstimate(null);
      setError(String(err));
    }
  }

  async function handleGetProjection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      const result = await getNetWorthProjection(
        selectedHouseholdId,
        Number(requiredString(form, 'start_year')),
        Number(requiredString(form, 'end_year')),
        {
          annualSpending: optionalString(form, 'annual_spending'),
          spendingInflationRate: optionalString(form, 'spending_inflation_rate'),
        },
      );
      setProjection(result);
    } catch (err: unknown) {
      setProjection(null);
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
      <header className="hero">
        <div>
          <p className="eyebrow">Netwise</p>
          <h1>Financial status from balance snapshots</h1>
          <p className="muted">Track household net worth without transaction categorization.</p>
        </div>
        <div className="selector-stack">
          {selectedUser && (
            <select
              value={selectedUserId}
              onChange={(event) => setSelectedUserId(event.target.value)}
              aria-label="Selected user"
            >
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.display_name}
                </option>
              ))}
            </select>
          )}
          {selectedHousehold && (
            <select
              value={selectedHouseholdId}
              onChange={(event) => setSelectedHouseholdId(event.target.value)}
              aria-label="Selected household"
            >
              {households.map((household) => (
                <option key={household.id} value={household.id}>
                  {household.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </header>

      {error && <div className="error">{error}</div>}
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

      {!loading && users.length > 0 && households.length === 0 && (
        <section className="card narrow">
          <h2>Create your household</h2>
          <p className="muted">This household will be owned by {selectedUser?.display_name ?? 'the selected user'}.</p>
          <form onSubmit={handleCreateHousehold} className="form-row">
            <input name="name" placeholder="Home" required />
            <button type="submit">Create</button>
          </form>
        </section>
      )}

      {selectedHousehold && (
        <>
          <section className="card">
            <div className="section-header">
              <div>
                <h2>People & household access</h2>
                <p className="muted">Switch users, switch households, and manage household memberships.</p>
              </div>
              <div className="management-actions">
                {adminToolsEnabled && (
                  <button type="button" className="secondary-button" onClick={handleDownloadHouseholdExport}>
                    Download household JSON
                  </button>
                )}
                <form onSubmit={handleCreateHousehold} className="form-row">
                  <input name="name" placeholder="New household name" required />
                  <button type="submit">Add household</button>
                </form>
                <form onSubmit={handleCreateUser} className="form-row">
                  <input name="display_name" placeholder="New user name" required />
                  <input name="email" type="email" placeholder="Email (optional)" />
                  <button type="submit">Add user</button>
                </form>
              </div>
            </div>
            <div className="member-list">
              {householdMembers.map((membership) => (
                <div key={membership.id} className="member-row">
                  <span>
                    <strong>{membership.user?.display_name ?? membership.user_id}</strong>
                    <span className="muted"> {membership.user?.email ?? ''}</span>
                  </span>
                  <span className="pill">{membership.role}</span>
                  <button type="button" className="secondary-button" onClick={() => handleRemoveHouseholdMember(membership.user_id)}>
                    Remove
                  </button>
                </div>
              ))}
            </div>
            {availableUsersForMembership.length > 0 && (
              <form onSubmit={handleAddHouseholdMember} className="form-row spaced-table">
                <select name="user_id" required defaultValue="">
                  <option value="" disabled>
                    Add user to household
                  </option>
                  {availableUsersForMembership.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.display_name}
                    </option>
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
                    Import a server-local FinTrack data directory into {selectedHousehold.name}. Expected files: <code>*-condition.toml</code>, <code>*-values.csv</code>, and optional <code>*-value-changes.csv</code>.
                  </p>
                </div>
              </div>
              <form onSubmit={handleImportFintrack} className="form-row">
                <input name="data_dir" placeholder="/Users/burm/code/fintrack/data-me" required />
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
                          <td>
                            {asset.accounts_created} created / {asset.accounts_existing} existing
                          </td>
                          <td>
                            {asset.snapshots_created} created / {asset.snapshots_updated} updated / {asset.snapshots_existing} unchanged
                          </td>
                          <td>
                            {asset.events_created} created / {asset.events_existing} existing
                          </td>
                          <td>
                            {asset.real_estate_profiles_created + asset.mortgage_profiles_created} created / {asset.real_estate_profiles_existing + asset.mortgage_profiles_existing} existing
                          </td>
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

          <section className="summary-grid">
            <div className="metric-card">
              <span>Net worth</span>
              <strong>{formatMoney(netWorth?.net_worth)}</strong>
            </div>
            <div className="metric-card">
              <span>Assets</span>
              <strong>{formatMoney(netWorth?.assets_total)}</strong>
            </div>
            <div className="metric-card">
              <span>Liabilities</span>
              <strong>{formatMoney(netWorth?.liabilities_total)}</strong>
            </div>
          </section>

          <section className="card">
            <div className="section-header">
              <div>
                <h2>Financial trajectory</h2>
                <p className="muted">Known historical snapshots, optional interpolated estimates, and projected future net worth in one view.</p>
              </div>
              <div className="toggle-group">
                <label className="inline-toggle">
                  <input
                    type="checkbox"
                    checked={showInterpolatedHistory}
                    onChange={(event) => setShowInterpolatedHistory(event.target.checked)}
                  />
                  Show interpolated estimates
                </label>
                <label className="inline-toggle">
                  <input
                    type="checkbox"
                    checked={showProjectionOnTrajectory}
                    onChange={(event) => setShowProjectionOnTrajectory(event.target.checked)}
                  />
                  Show projection after run
                </label>
              </div>
            </div>
            {history?.points.length ? (
              <>
                <HistoryChart
                  points={history.points}
                  projectionPoints={showProjectionOnTrajectory ? projection?.points ?? [] : []}
                />
                <table className="spaced-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Net worth</th>
                      <th>Assets</th>
                      <th>Liabilities</th>
                      <th>Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.points.map((point) => (
                      <tr key={`${point.as_of_date}-${point.estimated ? 'estimate' : 'snapshot'}`} className={point.estimated ? 'estimated-row' : undefined}>
                        <td>{point.as_of_date}</td>
                        <td>{formatMoney(point.net_worth)}</td>
                        <td>{formatMoney(point.assets_total)}</td>
                        <td>{formatMoney(point.liabilities_total)}</td>
                        <td>{point.estimated ? 'Estimate' : 'Snapshot'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <p className="muted">Add snapshots to see historical trend.</p>
            )}
          </section>

          <section className="card">
            <h2>What changed?</h2>
            <p className="muted">Break down each snapshot date by asset and liability category.</p>
            {breakdownHistory?.points.length ? (
              <div className="table-scroll">
                <table className="spaced-table breakdown-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      {breakdownCategories.assetCategories.map((category) => (
                        <th key={`asset-${category}`}>{category}</th>
                      ))}
                      {breakdownCategories.liabilityCategories.map((category) => (
                        <th key={`liability-${category}`}>{category} debt</th>
                      ))}
                      <th>Net worth</th>
                    </tr>
                  </thead>
                  <tbody>
                    {breakdownHistory.points.map((point) => (
                      <tr key={point.as_of_date}>
                        <td>{point.as_of_date}</td>
                        {breakdownCategories.assetCategories.map((category) => (
                          <td key={`${point.as_of_date}-asset-${category}`}>
                            {formatMoney(categoryBalance(point.asset_categories, category))}
                          </td>
                        ))}
                        {breakdownCategories.liabilityCategories.map((category) => (
                          <td key={`${point.as_of_date}-liability-${category}`}>
                            {formatMoney(categoryBalance(point.liability_categories, category))}
                          </td>
                        ))}
                        <td>{formatMoney(point.net_worth)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">Add snapshots to see category changes over time.</p>
            )}
          </section>

          <section className="card">
            <h2>Add household snapshot</h2>
            <p className="muted">Capture a snapshot day across many accounts. Empty balances are skipped; existing same-day snapshots are updated.</p>
            {accounts.length ? (
              <form onSubmit={handleCreateSnapshotBatch} className="stacked-form">
                <label>
                  Snapshot date
                  <input name="as_of_date" type="date" defaultValue={today()} required />
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
                      <input name={`balance:${account.id}`} inputMode="decimal" placeholder="Leave blank to skip" />
                    </div>
                  ))}
                </div>
                <button type="submit">Save household snapshot</button>
                {snapshotBatchMessage && <p className="success-message">{snapshotBatchMessage}</p>}
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
            {householdSnapshots.length ? (
              <table className="spaced-table">
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
                                <button type="button" onClick={() => handleUpdateSnapshot(snapshot)}>
                                  Save
                                </button>
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
                                <button type="button" className="danger-button" onClick={() => handleDeleteSnapshot(snapshot)}>
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
            <h2>Projection</h2>
            <p className="muted">Project net worth from current balances, account yields, mortgages, estimated spending, projected income, taxes, and future projection events.</p>
            <form onSubmit={handleGetProjection} className="form-row">
              <input
                name="start_year"
                inputMode="numeric"
                placeholder="Start year"
                defaultValue={new Date().getFullYear()}
                required
              />
              <input
                name="end_year"
                inputMode="numeric"
                placeholder="End year"
                defaultValue={new Date().getFullYear() + 10}
                required
              />
              <input
                name="annual_spending"
                inputMode="decimal"
                placeholder="Annual spending override"
              />
              <input
                name="spending_inflation_rate"
                inputMode="decimal"
                placeholder="Spending inflation, e.g. 0.03"
                defaultValue="0.03"
              />
              <button type="submit">Run projection</button>
            </form>
            {projection?.points.length ? (
              <table className="spaced-table">
                <thead>
                  <tr>
                    <th>Year</th>
                    <th>Net worth</th>
                    <th>Assets</th>
                    <th>Liabilities</th>
                    <th>Income</th>
                    <th>Taxes</th>
                    <th>Spending</th>
                    <th>Net cash flow</th>
                  </tr>
                </thead>
                <tbody>
                  {projection.points.map((point) => (
                    <tr key={point.year}>
                      <td>{point.year}</td>
                      <td>{formatMoney(point.net_worth)}</td>
                      <td>{formatMoney(point.assets_total)}</td>
                      <td>{formatMoney(point.liabilities_total)}</td>
                      <td>{formatMoney(point.projected_income)}</td>
                      <td>{formatMoney(point.projected_taxes)}</td>
                      <td>{formatMoney(point.projected_spending)}</td>
                      <td>{formatMoney(point.net_cash_flow)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">Run a projection to see future net worth points.</p>
            )}
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Income sources</h2>
              {incomeSources.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Amount</th>
                      <th>Frequency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incomeSources.map((source) => (
                      <tr key={source.id}>
                        <td>{source.name}</td>
                        <td>{source.income_type}</td>
                        <td>{formatMoney(source.amount)}</td>
                        <td>{source.frequency}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No income sources yet.</p>
              )}
            </div>

            <div className="card">
              <h2>Annual tax records</h2>
              {taxRecords.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Year</th>
                      <th>Gross income</th>
                      <th>Taxes paid</th>
                      <th>Effective rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {taxRecords.map((record) => (
                      <tr key={record.id}>
                        <td>{record.tax_year}</td>
                        <td>{formatMoney(record.gross_income)}</td>
                        <td>{formatMoney(record.total_taxes_paid)}</td>
                        <td>{record.effective_tax_rate ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No tax records yet.</p>
              )}
            </div>
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Add income source</h2>
              <form onSubmit={handleCreateIncomeSource} className="stacked-form">
                <input name="income_name" placeholder="Salary" required />
                <input name="income_type" placeholder="salary / bonus / other" />
                <input name="amount" inputMode="decimal" placeholder="Amount per pay period" required />
                <select name="frequency" defaultValue="monthly" required>
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Biweekly</option>
                  <option value="semimonthly">Semimonthly</option>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="annually">Annually</option>
                </select>
                <label>
                  Start date
                  <input name="start_date" type="date" defaultValue={today()} required />
                </label>
                <label>
                  End date
                  <input name="end_date" type="date" />
                </label>
                <input name="growth_rate" inputMode="decimal" placeholder="Growth rate, e.g. 0.03" />
                <button type="submit">Add income source</button>
              </form>
            </div>

            <div className="card">
              <h2>Add tax record</h2>
              <form onSubmit={handleCreateTaxRecord} className="stacked-form">
                <input name="tax_year" inputMode="numeric" placeholder="Tax year" required />
                <input name="gross_income" inputMode="decimal" placeholder="Gross income" />
                <input name="total_taxes_paid" inputMode="decimal" placeholder="Total taxes paid" required />
                <input name="refund_or_amount_due" inputMode="decimal" placeholder="Refund or amount due" />
                <input name="notes" placeholder="Notes" />
                <button type="submit">Add tax record</button>
              </form>
            </div>
          </section>

          <section className="card">
            <h2>Expense estimate</h2>
            <p className="muted">Estimate annual living expense from gross income, taxes, and net worth change.</p>
            <form onSubmit={handleGetExpenseEstimate} className="form-row">
              <input
                name="tax_year"
                inputMode="numeric"
                placeholder="Tax year"
                defaultValue={taxRecords[0]?.tax_year ?? new Date().getFullYear() - 1}
                required
              />
              <button type="submit">Estimate expenses</button>
            </form>
            {expenseEstimate && (
              <section className="summary-grid compact-summary">
                <div className="metric-card">
                  <span>Estimated expense</span>
                  <strong>{formatMoney(expenseEstimate.estimated_living_expense)}</strong>
                </div>
                <div className="metric-card">
                  <span>Net worth change</span>
                  <strong>{formatMoney(expenseEstimate.net_worth_change)}</strong>
                </div>
                <div className="metric-card">
                  <span>Adjustments</span>
                  <strong>{formatMoney(expenseEstimate.adjustment_total)}</strong>
                </div>
              </section>
            )}
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Real estate</h2>
              {properties.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Property</th>
                      <th>Type</th>
                      <th>Purchase price</th>
                      <th>Appreciation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {properties.map((property) => (
                      <tr key={property.id}>
                        <td>{accountNameById.get(property.account_id) ?? property.account_id}</td>
                        <td>{property.property_type}</td>
                        <td>{formatMoney(property.purchase_price)}</td>
                        <td>{property.expected_appreciation_rate ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No property profiles yet.</p>
              )}
            </div>

            <div className="card">
              <h2>Mortgages</h2>
              {mortgages.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Mortgage</th>
                      <th>Property</th>
                      <th>Principal</th>
                      <th>Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mortgages.map((mortgage) => (
                      <tr key={mortgage.id}>
                        <td>{accountNameById.get(mortgage.liability_account_id) ?? mortgage.liability_account_id}</td>
                        <td>
                          {mortgage.property_account_id
                            ? accountNameById.get(mortgage.property_account_id) ?? mortgage.property_account_id
                            : '—'}
                        </td>
                        <td>{formatMoney(mortgage.original_principal)}</td>
                        <td>{mortgage.interest_rate}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No mortgage profiles yet.</p>
              )}
            </div>
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Add property</h2>
              <p className="muted">Creates a real estate asset account, property profile, and optional valuation snapshot.</p>
              <form onSubmit={handleCreateProperty} className="stacked-form">
                <input name="property_name" placeholder="Primary residence" required />
                <select name="property_type" defaultValue="residence">
                  <option value="residence">Residence</option>
                  <option value="rental">Rental</option>
                  <option value="land">Land</option>
                  <option value="other">Other</option>
                </select>
                <label>
                  Purchase date
                  <input name="purchase_date" type="date" />
                </label>
                <input name="purchase_price" inputMode="decimal" placeholder="Purchase price" />
                <input name="down_payment" inputMode="decimal" placeholder="Down payment" />
                <input name="expected_appreciation_rate" inputMode="decimal" placeholder="Expected appreciation rate, e.g. 0.03" />
                <input name="property_tax_annual" inputMode="decimal" placeholder="Annual property tax" />
                <input name="insurance_annual" inputMode="decimal" placeholder="Annual insurance" />
                <input name="maintenance_rate" inputMode="decimal" placeholder="Maintenance rate, e.g. 0.01" />
                <input name="hoa_monthly" inputMode="decimal" placeholder="Monthly HOA" />
                <input name="current_value" inputMode="decimal" placeholder="Current valuation snapshot" />
                <label>
                  Valuation date
                  <input name="valuation_date" type="date" defaultValue={today()} />
                </label>
                <button type="submit">Add property</button>
              </form>
            </div>

            <div className="card">
              <h2>Add mortgage</h2>
              <p className="muted">Creates a mortgage liability account, mortgage profile, and initial balance snapshot.</p>
              <form onSubmit={handleCreateMortgage} className="stacked-form">
                <input name="mortgage_name" placeholder="Primary residence mortgage" required />
                <select name="property_account_id" defaultValue="">
                  <option value="">No linked property</option>
                  {propertyAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
                <input name="original_principal" inputMode="decimal" placeholder="Original principal" required />
                <input name="interest_rate" inputMode="decimal" placeholder="Interest rate, e.g. 0.065" required />
                <input name="term_months" inputMode="numeric" placeholder="Term months, e.g. 360" required />
                <label>
                  Start date
                  <input name="start_date" type="date" required />
                </label>
                <input name="monthly_payment" inputMode="decimal" placeholder="Monthly payment" />
                <select name="rate_type" defaultValue="fixed">
                  <option value="fixed">Fixed</option>
                  <option value="adjustable">Adjustable</option>
                </select>
                <input name="current_balance" inputMode="decimal" placeholder="Current balance; defaults to original principal" />
                <label>
                  Balance date
                  <input name="balance_date" type="date" />
                </label>
                <button type="submit">Add mortgage</button>
              </form>
            </div>
          </section>

          <section className="card">
            <h2>Accounts</h2>
            {netWorth?.accounts.length ? (
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Kind</th>
                    <th>Category</th>
                    <th>Yield</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {netWorth.accounts.map((account) => (
                    <tr key={account.account_id}>
                      <td>{account.name}</td>
                      <td>{account.account_kind}</td>
                      <td>{account.category}</td>
                      <td>{accounts.find((item) => item.id === account.account_id)?.expected_annual_yield ?? '—'}</td>
                      <td>{formatMoney(account.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">No accounts yet.</p>
            )}
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Projection events</h2>
              {accountEvents.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Account</th>
                      <th>Type</th>
                      <th>Amount</th>
                      <th>Behavior</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accountEvents.map((event) => (
                      <tr key={event.id}>
                        <td>{event.event_date}</td>
                        <td>{accountNameById.get(event.account_id) ?? event.account_id}</td>
                        <td>{event.event_type}</td>
                        <td>{formatMoney(event.amount)}</td>
                        <td>{event.projection_behavior}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No projection events yet.</p>
              )}
            </div>

            <div className="card">
              <h2>Add projection event</h2>
              <p className="muted">Capture planned future contributions, withdrawals, purchases, sales, and adjustments.</p>
              <form onSubmit={handleCreateAccountEvent} className="stacked-form">
                <select name="account_id" required defaultValue="">
                  <option value="" disabled>
                    Select account
                  </option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
                <label>
                  Event date
                  <input name="event_date" type="date" defaultValue={today()} required />
                </label>
                <input name="amount" inputMode="decimal" placeholder="Amount" required />
                <select name="event_type" defaultValue="manual_projection_adjustment" required>
                  <option value="contribution">Contribution</option>
                  <option value="withdrawal">Withdrawal</option>
                  <option value="transfer">Transfer</option>
                  <option value="large_purchase">Large purchase</option>
                  <option value="asset_sale">Asset sale</option>
                  <option value="gift">Gift</option>
                  <option value="inheritance">Inheritance</option>
                  <option value="tax_payment">Tax payment</option>
                  <option value="account_added">Account added</option>
                  <option value="account_removed">Account removed</option>
                  <option value="manual_projection_adjustment">Manual projection adjustment</option>
                </select>
                <select name="projection_behavior" defaultValue="projection_only" required>
                  <option value="projection_only">Projection only</option>
                  <option value="historical_and_projection">Historical and projection</option>
                  <option value="historical_only">Historical only</option>
                </select>
                <input name="description" placeholder="Description" />
                <button type="submit">Add projection event</button>
              </form>
            </div>
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Add account</h2>
              <form onSubmit={handleCreateAccount} className="stacked-form">
                <input name="name" placeholder="Fidelity 401k" required />
                <select name="account_kind" defaultValue="asset">
                  <option value="asset">Asset</option>
                  <option value="liability">Liability</option>
                </select>
                <input name="category" placeholder="retirement / real_estate / mortgage" required />
                <input name="liquidity_class" placeholder="retirement_liquid / real_estate / liability" required />
                <input name="expected_annual_yield" inputMode="decimal" placeholder="Expected annual yield, e.g. 0.05" />
                <button type="submit">Add account</button>
              </form>
            </div>

            <div className="card">
              <h2>Add snapshot</h2>
              <form onSubmit={handleCreateSnapshot} className="stacked-form">
                <select name="account_id" required defaultValue="">
                  <option value="" disabled>
                    Select account
                  </option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
                <input name="as_of_date" type="date" defaultValue={today()} required />
                <input name="balance" placeholder="100000.00" required />
                <button type="submit">Add snapshot</button>
              </form>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export default App;
