import { FormEvent, Suspense, lazy, type ReactNode, useEffect, useMemo, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import {
  Account,
  AccountEvent,
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
  ProjectionSettings,
  RealEstateLiquidationStrategy,
  RealEstateProperty,
  RealEstateSale,
  RetirementTaxTreatment,
  User,
  addHouseholdMember,
  createAccount,
  createAccountEvent,
  createAnnualTaxRecord,
  createHousehold,
  createIncomeSource,
  createMortgageProfile,
  createRealEstateProperty,
  createRealEstateSale,
  createSnapshot,
  createSnapshotBatch,
  createUser,
  deleteAccountEvent,
  deleteSnapshot,
  deleteRealEstateLiquidationStrategy,
  deleteRealEstateSale,
  exportHousehold,
  getCapabilities,
  getHistoricalTrend,
  getNetWorth,
  getNetWorthBreakdownHistory,
  getNetWorthProjection,
  getProjectionSettings,
  importFintrack,
  listAccounts,
  listAccountEvents,
  listAnnualTaxRecords,
  listHouseholds,
  listHouseholdMembers,
  listHouseholdSnapshots,
  listIncomeSources,
  listMortgageProfiles,
  listRealEstateLiquidationStrategies,
  listRealEstateProperties,
  listRealEstateSales,
  listUsers,
  removeHouseholdMember,
  updateAccount,
  updateAccountEvent,
  updateRealEstateProperty,
  updateSnapshot,
  upsertProjectionSettings,
  upsertRealEstateLiquidationStrategy,
} from './api';
import {
  AppHeader,
  AppNavigation,
  ViewHeading,
  type AppView,
} from './components/AppShell';
import type { AccountEditDraft } from './pages/AssetsPage';
import type { AccountEventDraft } from './pages/PlanningPage';
import type { SnapshotEditDraft } from './pages/UpdateBalancesPage';
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

function WorkspaceView({ view, children }: { view: AppView; children: ReactNode }) {
  return (
    <>
      <ViewHeading activeView={view} />
      <Suspense fallback={<div className="card" role="status">Loading page…</div>}>
        {children}
      </Suspense>
    </>
  );
}

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [households, setHouseholds] = useState<Household[]>([]);
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string>('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountEditDraft, setAccountEditDraft] = useState<AccountEditDraft | null>(null);
  const [accountEvents, setAccountEvents] = useState<AccountEvent[]>([]);
  const [accountEventDraft, setAccountEventDraft] = useState<AccountEventDraft | null>(null);
  const [householdSnapshots, setHouseholdSnapshots] = useState<HouseholdSnapshot[]>([]);
  const [householdMembers, setHouseholdMembers] = useState<HouseholdMembership[]>([]);
  const [snapshotAccountFilter, setSnapshotAccountFilter] = useState<string>('');
  const [snapshotEditDraft, setSnapshotEditDraft] = useState<SnapshotEditDraft | null>(null);
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [history, setHistory] = useState<NetWorthHistory | null>(null);
  const [breakdownHistory, setBreakdownHistory] = useState<NetWorthBreakdownHistory | null>(null);
  const [properties, setProperties] = useState<RealEstateProperty[]>([]);
  const [propertyEditId, setPropertyEditId] = useState<string>('');
  const [realEstateSales, setRealEstateSales] = useState<RealEstateSale[]>([]);
  const [liquidationStrategies, setLiquidationStrategies] = useState<RealEstateLiquidationStrategy[]>([]);
  const [mortgages, setMortgages] = useState<MortgageProfile[]>([]);
  const [incomeSources, setIncomeSources] = useState<IncomeSource[]>([]);
  const [taxRecords, setTaxRecords] = useState<AnnualTaxRecord[]>([]);
  const [projection, setProjection] = useState<NetWorthProjection | null>(null);
  const [projectionSettings, setProjectionSettings] = useState<ProjectionSettings | null>(null);
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
      realEstateSaleList,
      liquidationStrategyList,
      mortgageList,
      incomeSourceList,
      taxRecordList,
      snapshotList,
      breakdownResult,
      memberList,
      projectionSettingsResult,
    ] = await Promise.all([
      listAccounts(householdId),
      getNetWorth(householdId),
      getHistoricalTrend(householdId, showInterpolatedHistory),
      listRealEstateProperties(householdId),
      listRealEstateSales(householdId),
      listRealEstateLiquidationStrategies(householdId),
      listMortgageProfiles(householdId),
      listIncomeSources(householdId),
      listAnnualTaxRecords(householdId),
      listHouseholdSnapshots(householdId, snapshotAccountFilter || undefined),
      getNetWorthBreakdownHistory(householdId),
      listHouseholdMembers(householdId),
      getProjectionSettings(householdId),
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
    setRealEstateSales(realEstateSaleList);
    setLiquidationStrategies(liquidationStrategyList);
    setMortgages(mortgageList);
    setIncomeSources(incomeSourceList);
    setTaxRecords(taxRecordList);
    setProjectionSettings(projectionSettingsResult);
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
    setProjection(null);
    setProjectionSettings(null);
    setAccountEditDraft(null);
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

  function startEditAccount(account: Account) {
    setAccountEditDraft({
      id: account.id,
      name: account.name,
      institution_name: account.institution_name ?? '',
      account_kind: account.account_kind,
      category: account.category,
      liquidity_class: account.liquidity_class,
      retirement_tax_treatment: account.retirement_tax_treatment ?? '',
      expected_annual_yield: account.expected_annual_yield ?? '',
      liquidation_expense_rate: account.liquidation_expense_rate ?? '',
      currency: account.currency,
      is_active: account.is_active,
    });
  }

  async function handleSaveAccountEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId || !accountEditDraft) return;
    setError('');
    try {
      await updateAccount(accountEditDraft.id, {
        name: accountEditDraft.name.trim(),
        institution_name: accountEditDraft.institution_name.trim() || null,
        account_kind: accountEditDraft.account_kind,
        category: accountEditDraft.category.trim(),
        liquidity_class: accountEditDraft.liquidity_class.trim(),
        retirement_tax_treatment: accountEditDraft.retirement_tax_treatment || null,
        expected_annual_yield: accountEditDraft.expected_annual_yield.trim() || null,
        liquidation_expense_rate: accountEditDraft.liquidation_expense_rate.trim() || null,
        currency: accountEditDraft.currency.trim().toUpperCase(),
        is_active: accountEditDraft.is_active,
      });
      setAccountEditDraft(null);
      await refreshDashboard(selectedHouseholdId);
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
        retirement_tax_treatment: optionalString(
          form,
          'retirement_tax_treatment',
        ) as RetirementTaxTreatment | undefined,
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

  function startNewAccountEventDraft() {
    setAccountEventDraft({
      account_id: accounts[0]?.id ?? '',
      event_date: today(),
      amount: '',
      currency: 'USD',
      event_type: 'manual_projection_adjustment',
      description: '',
      projection_behavior: 'projection_only',
    });
  }

  function startEditAccountEventDraft(accountEvent: AccountEvent) {
    setAccountEventDraft({
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

  async function handleSaveAccountEventDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId || !accountEventDraft) return;
    setError('');
    try {
      const payload = {
        account_id: accountEventDraft.account_id,
        event_date: accountEventDraft.event_date,
        amount: accountEventDraft.amount,
        currency: accountEventDraft.currency,
        event_type: accountEventDraft.event_type,
        description: accountEventDraft.description || null,
        projection_behavior: accountEventDraft.projection_behavior,
      };
      if (accountEventDraft.id && accountEventDraft.original_account_id) {
        await updateAccountEvent(accountEventDraft.original_account_id, accountEventDraft.id, payload);
      } else {
        await createAccountEvent(accountEventDraft.account_id, {
          event_date: payload.event_date,
          amount: payload.amount,
          currency: payload.currency,
          event_type: payload.event_type,
          description: accountEventDraft.description || undefined,
          projection_behavior: payload.projection_behavior,
        });
      }
      setAccountEventDraft(null);
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleDeleteAccountEvent(accountEvent: AccountEvent) {
    if (!selectedHouseholdId) return;
    const confirmed = window.confirm(
      `Delete ${accountEvent.event_type} event from ${accountEvent.event_date}?`,
    );
    if (!confirmed) return;
    setError('');
    try {
      await deleteAccountEvent(accountEvent.account_id, accountEvent.id);
      if (accountEventDraft?.id === accountEvent.id) setAccountEventDraft(null);
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleUpdateProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId || !propertyEditId) return;
    const form = new FormData(event.currentTarget);
    try {
      await updateRealEstateProperty(propertyEditId, {
        property_type: requiredString(form, 'property_type'),
        is_rental: form.get('is_rental') === 'on',
        rental_start_date: optionalString(form, 'rental_start_date') || null,
        monthly_market_rent: optionalString(form, 'monthly_market_rent') || null,
        other_monthly_income: optionalString(form, 'other_monthly_income') || null,
        rent_growth_rate: optionalString(form, 'rent_growth_rate') || null,
        vacancy_rate: optionalString(form, 'vacancy_rate') || null,
        management_fee_rate: optionalString(form, 'management_fee_rate') || null,
        property_tax_annual: optionalString(form, 'property_tax_annual') || null,
        insurance_annual: optionalString(form, 'insurance_annual') || null,
        tax_and_insurance_annual: optionalString(form, 'tax_and_insurance_annual') || null,
        maintenance_rate: optionalString(form, 'maintenance_rate') || null,
        hoa_monthly: optionalString(form, 'hoa_monthly') || null,
        utilities_annual: optionalString(form, 'utilities_annual') || null,
        other_operating_expense_annual: optionalString(form, 'other_operating_expense_annual') || null,
        capital_reserve_rate: optionalString(form, 'capital_reserve_rate') || null,
        rental_deposit_account_id: optionalString(form, 'rental_deposit_account_id') || null,
      });
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
        tax_and_insurance_annual: optionalString(form, 'tax_and_insurance_annual'),
        maintenance_rate: optionalString(form, 'maintenance_rate'),
        hoa_monthly: optionalString(form, 'hoa_monthly'),
        is_rental: form.get('is_rental') === 'on',
        rental_start_date: optionalString(form, 'rental_start_date'),
        monthly_market_rent: optionalString(form, 'monthly_market_rent'),
        other_monthly_income: optionalString(form, 'other_monthly_income'),
        rent_growth_rate: optionalString(form, 'rent_growth_rate'),
        vacancy_rate: optionalString(form, 'vacancy_rate'),
        management_fee_rate: optionalString(form, 'management_fee_rate'),
        utilities_annual: optionalString(form, 'utilities_annual'),
        other_operating_expense_annual: optionalString(form, 'other_operating_expense_annual'),
        capital_reserve_rate: optionalString(form, 'capital_reserve_rate'),
        rental_deposit_account_id: optionalString(form, 'rental_deposit_account_id'),
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

  async function handleCreateRealEstateSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createRealEstateSale({
        property_account_id: requiredString(form, 'property_account_id'),
        sale_date: requiredString(form, 'sale_date'),
        gross_sale_price: requiredString(form, 'gross_sale_price'),
        proceeds_account_id: optionalString(form, 'proceeds_account_id'),
        selling_expense_rate: optionalString(form, 'selling_expense_rate'),
        estimated_tax_rate: requiredString(form, 'estimated_tax_rate'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleDeleteRealEstateSale(sale: RealEstateSale) {
    if (!selectedHouseholdId) return;
    if (!window.confirm(`Delete the planned sale on ${sale.sale_date}?`)) return;
    setError('');
    try {
      await deleteRealEstateSale(sale.id);
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleUpsertLiquidationStrategy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    const propertyAccountId = requiredString(form, 'automatic_property_account_id');
    try {
      await upsertRealEstateLiquidationStrategy(propertyAccountId, {
        enabled: form.get('automatic_enabled') === 'on',
        optimization_mode: requiredString(form, 'automatic_optimization_mode') as 'liquidity_shortfall' | 'maximize_liquid_runway',
        priority: Number(requiredString(form, 'automatic_priority')),
        earliest_sale_date: optionalString(form, 'automatic_earliest_sale_date'),
        proceeds_account_id: optionalString(form, 'automatic_proceeds_account_id'),
        selling_expense_rate: optionalString(form, 'automatic_selling_expense_rate'),
        estimated_tax_rate: requiredString(form, 'automatic_estimated_tax_rate'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleDeleteLiquidationStrategy(strategy: RealEstateLiquidationStrategy) {
    if (!selectedHouseholdId) return;
    if (!window.confirm('Delete this automatic property sale strategy?')) return;
    setError('');
    try {
      await deleteRealEstateLiquidationStrategy(strategy.property_account_id);
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
        deposit_account_id: optionalString(form, 'deposit_account_id'),
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

  async function handleGetProjection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    setError('');
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
        spending_inflation_rate: optionalString(form, 'settings_spending_inflation_rate'),
        spending_account_id: optionalString(form, 'settings_spending_account_id'),
        tax_account_id: optionalString(form, 'settings_tax_account_id'),
      });
      setProjectionSettings(result);
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
        users={users}
        selectedUser={selectedUser}
        selectedUserId={selectedUserId}
        onSelectUser={setSelectedUserId}
        households={households}
        selectedHousehold={selectedHousehold}
        selectedHouseholdId={selectedHouseholdId}
        onSelectHousehold={setSelectedHouseholdId}
      />

      {selectedHousehold && <AppNavigation />}

      {error && <div className="error" role="alert">{error}</div>}
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
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route
            path="/overview"
            element={
              <WorkspaceView view="overview">
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
              <WorkspaceView view="update">
                <UpdateBalancesPage
                  accounts={accounts}
                  latestBalanceByAccountId={latestBalanceByAccountId}
                  defaultDate={today()}
                  snapshotBatchMessage={snapshotBatchMessage}
                  onCreateSnapshotBatch={handleCreateSnapshotBatch}
                  householdSnapshots={householdSnapshots}
                  snapshotAccountFilter={snapshotAccountFilter}
                  onSnapshotAccountFilter={setSnapshotAccountFilter}
                  snapshotEditDraft={snapshotEditDraft}
                  onSnapshotEditDraft={setSnapshotEditDraft}
                  onUpdateSnapshot={handleUpdateSnapshot}
                  onDeleteSnapshot={handleDeleteSnapshot}
                  onCreateSnapshot={handleCreateSnapshot}
                />
              </WorkspaceView>
            }
          />
          <Route
            path="/plan"
            element={
              <WorkspaceView view="plan">
                <PlanningPage
                  defaultDate={today()}
                  accounts={accounts}
                  assetAccounts={assetAccounts}
                  propertyAccounts={propertyAccounts}
                  accountNameById={accountNameById}
                  liquidationStrategies={liquidationStrategies}
                  onDeleteLiquidationStrategy={handleDeleteLiquidationStrategy}
                  onUpsertLiquidationStrategy={handleUpsertLiquidationStrategy}
                  projectionSettings={projectionSettings}
                  onSaveProjectionSettings={handleSaveProjectionSettings}
                  onGetProjection={handleGetProjection}
                  incomeSources={incomeSources}
                  taxRecords={taxRecords}
                  projection={projection}
                  onCreateIncomeSource={handleCreateIncomeSource}
                  onCreateTaxRecord={handleCreateTaxRecord}
                  realEstateSales={realEstateSales}
                  onDeleteRealEstateSale={handleDeleteRealEstateSale}
                  onCreateRealEstateSale={handleCreateRealEstateSale}
                  accountEvents={accountEvents}
                  accountEventDraft={accountEventDraft}
                  onAccountEventDraft={setAccountEventDraft}
                  onStartNewAccountEvent={startNewAccountEventDraft}
                  onStartEditAccountEvent={startEditAccountEventDraft}
                  onSaveAccountEvent={handleSaveAccountEventDraft}
                  onDeleteAccountEvent={handleDeleteAccountEvent}
                />
              </WorkspaceView>
            }
          />
          <Route
            path="/assets"
            element={
              <WorkspaceView view="assets">
                <AssetsPage
                  defaultDate={today()}
                  accounts={accounts}
                  assetAccounts={assetAccounts}
                  propertyAccounts={propertyAccounts}
                  properties={properties}
                  mortgages={mortgages}
                  propertyEditId={propertyEditId}
                  onPropertyEditId={setPropertyEditId}
                  accountNameById={accountNameById}
                  latestBalanceByAccountId={latestBalanceByAccountId}
                  onUpdateProperty={handleUpdateProperty}
                  onCreateProperty={handleCreateProperty}
                  onCreateMortgage={handleCreateMortgage}
                  accountEditDraft={accountEditDraft}
                  onAccountEditDraft={setAccountEditDraft}
                  onSaveAccountEdit={handleSaveAccountEdit}
                  onStartEditAccount={startEditAccount}
                  onCreateAccount={handleCreateAccount}
                />
              </WorkspaceView>
            }
          />
          <Route
            path="/settings"
            element={
              <WorkspaceView view="settings">
                <HouseholdSettingsPage
                  household={selectedHousehold}
                  members={householdMembers}
                  availableUsers={availableUsersForMembership}
                  adminToolsEnabled={adminToolsEnabled}
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
