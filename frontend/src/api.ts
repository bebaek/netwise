export type Household = {
  id: string;
  name: string;
};

export type User = {
  id: string;
  display_name: string;
  email: string | null;
  created_at: string;
  updated_at: string;
};

export type AuthStatus = {
  setup_required: boolean;
  public_signup_enabled: boolean;
  user: User | null;
};

export type HouseholdMembership = {
  id: string;
  household_id: string;
  user_id: string;
  role: string;
  created_at: string;
  user: User | null;
};

export type Capabilities = {
  admin_tools_enabled: boolean;
  fintrack_import_enabled: boolean;
};

export type HouseholdExport = {
  schema: string;
  exported_at: string;
  household: Record<string, unknown>;
  members: Array<Record<string, unknown>>;
  accounts: Array<Record<string, unknown>>;
  snapshots: Array<Record<string, unknown>>;
  account_events: Array<Record<string, unknown>>;
  real_estate_properties: Array<Record<string, unknown>>;
  mortgage_profiles: Array<Record<string, unknown>>;
  income_sources: Array<Record<string, unknown>>;
  annual_tax_records: Array<Record<string, unknown>>;
};

export type FintrackImportResult = {
  household_id: string;
  data_dir: string;
  dry_run: boolean;
  accounts_created: number;
  accounts_existing: number;
  snapshots_created: number;
  snapshots_updated: number;
  snapshots_existing: number;
  events_created: number;
  events_existing: number;
  real_estate_profiles_created: number;
  real_estate_profiles_existing: number;
  mortgage_profiles_created: number;
  mortgage_profiles_existing: number;
  assets: Array<{
    name: string;
    kind: string;
    account_id: string | null;
    liability_account_id: string | null;
    accounts_created: number;
    accounts_existing: number;
    snapshots_created: number;
    snapshots_updated: number;
    snapshots_existing: number;
    events_created: number;
    events_existing: number;
    real_estate_profiles_created: number;
    real_estate_profiles_existing: number;
    mortgage_profiles_created: number;
    mortgage_profiles_existing: number;
    warnings: string[];
  }>;
};

export type RetirementTaxTreatment = 'traditional' | 'roth' | 'after_tax';

export type Account = {
  id: string;
  household_id: string;
  name: string;
  institution_name: string | null;
  account_kind: 'asset' | 'liability';
  category: string;
  liquidity_class: string;
  retirement_tax_treatment: RetirementTaxTreatment | null;
  expected_annual_yield: string | null;
  liquidation_expense_rate: string | null;
  cost_basis: string | null;
  currency: string;
  is_active: boolean;
};

export type NetWorth = {
  household_id: string;
  net_worth: string;
  assets_total: string;
  liabilities_total: string;
  accounts: Array<{
    account_id: string;
    name: string;
    account_kind: string;
    category: string;
    liquidity_class: string;
    balance: string | null;
    signed_balance: string;
  }>;
};

export type NetWorthHistory = {
  household_id: string;
  points: Array<{
    as_of_date: string;
    net_worth: string;
    assets_total: string;
    liabilities_total: string;
    estimated?: boolean;
    method?: string | null;
  }>;
};

export type NetWorthBreakdownHistory = {
  household_id: string;
  points: Array<{
    as_of_date: string;
    net_worth: string;
    assets_total: string;
    liabilities_total: string;
    asset_categories: Array<{ category: string; balance: string }>;
    liability_categories: Array<{ category: string; balance: string }>;
  }>;
};

export type SnapshotBatch = {
  household_id: string;
  as_of_date: string;
  created_count: number;
  updated_count: number;
  snapshots: Array<{
    id: string;
    household_id: string;
    account_id: string;
    as_of_date: string;
    balance: string;
    currency: string;
    source: string;
    confidence_level: string | null;
    created_at: string;
  }>;
};

export type HouseholdSnapshot = SnapshotBatch['snapshots'][number] & {
  account_name: string;
  account_kind: string;
  account_category: string;
};

export type AccountEvent = {
  id: string;
  household_id: string;
  account_id: string;
  event_date: string;
  amount: string;
  currency: string;
  event_type: string;
  description: string | null;
  projection_behavior: string;
  scenario_id: string | null;
  created_at: string;
  updated_at: string;
};

export type RealEstateProperty = {
  id: string;
  household_id: string;
  account_id: string;
  property_type: string;
  purchase_date: string | null;
  purchase_price: string | null;
  adjusted_tax_basis: string | null;
  down_payment: string | null;
  expected_appreciation_rate: string | null;
  property_tax_annual: string | null;
  insurance_annual: string | null;
  tax_and_insurance_annual: string | null;
  maintenance_rate: string | null;
  hoa_monthly: string | null;
  is_rental: boolean;
  rental_start_date: string | null;
  monthly_market_rent: string | null;
  other_monthly_income: string | null;
  rent_growth_rate: string | null;
  vacancy_rate: string | null;
  management_fee_rate: string | null;
  utilities_annual: string | null;
  other_operating_expense_annual: string | null;
  capital_reserve_rate: string | null;
  rental_deposit_account_id: string | null;
  created_at: string;
  updated_at: string;
};

export type RealEstateAnalytics = {
  property_id: string;
  account_id: string;
  property_name: string;
  valuation_date: string | null;
  current_value: string | null;
  purchase_date: string | null;
  purchase_price: string | null;
  expected_appreciation_rate: string | null;
  appreciation_amount: string | null;
  appreciation_rate: string | null;
  annualized_appreciation_rate: string | null;
  mortgage_balance: string | null;
  mortgage_balance_estimated: boolean;
  equity: string | null;
  estimated_annual_rental_income: string | null;
  estimated_noi: string | null;
  estimated_annual_cash_flow: string | null;
  gross_rental_yield: string | null;
  cap_rate: string | null;
  cash_on_cash_return: string | null;
  valuation_history: Array<{ as_of_date: string; value: string }>;
  limitations: string[];
};

export type RealEstateSale = {
  id: string;
  household_id: string;
  scenario_id: string;
  property_account_id: string;
  sale_date: string;
  gross_sale_price: string;
  proceeds_account_id: string;
  selling_expense_rate: string | null;
  estimated_tax_rate: string;
  created_at: string;
  updated_at: string;
};

export type RealEstateLiquidationStrategy = {
  id: string;
  household_id: string;
  scenario_id: string;
  property_account_id: string;
  enabled: boolean;
  optimization_mode: 'liquidity_shortfall' | 'maximize_liquid_runway';
  priority: number;
  earliest_sale_date: string | null;
  proceeds_account_id: string;
  selling_expense_rate: string | null;
  estimated_tax_rate: string;
  created_at: string;
  updated_at: string;
};

export type MortgageProfile = {
  id: string;
  household_id: string;
  liability_account_id: string;
  property_account_id: string | null;
  original_principal: string;
  interest_rate: string;
  term_months: number;
  start_date: string;
  monthly_payment: string | null;
  rate_type: string;
  created_at: string;
  updated_at: string;
};

export type IncomeSource = {
  id: string;
  household_id: string;
  scenario_id: string;
  name: string;
  income_type: string;
  amount: string;
  currency: string;
  frequency: string;
  start_date: string;
  end_date: string | null;
  growth_rate: string | null;
  deposit_account_id: string | null;
  created_at: string;
  updated_at: string;
};

export type HouseholdPerson = {
  id: string;
  household_id: string;
  name: string;
  date_of_birth: string;
  created_at: string;
  updated_at: string;
};

export type SocialSecurityEstimate = {
  id: string;
  household_id: string;
  scenario_id: string;
  person_id: string;
  income_source_id: string;
  calculation_mode: 'manual' | 'ballpark';
  claiming_date: string;
  current_covered_earnings: string | null;
  completed_work_years: number | null;
  expected_work_end_date: string | null;
  earnings_pattern: 'lower' | 'steady' | 'rising' | null;
  manual_monthly_benefit: string | null;
  cola_rate: string;
  estimated_monthly_benefit: string;
  lower_monthly_benefit: string;
  upper_monthly_benefit: string;
  full_retirement_age_months: number;
  benefit_at_full_retirement_age: string;
  calculation_version: string;
  law_assumption_year: number;
  created_at: string;
  updated_at: string;
};

export type SocialSecurityEstimateInput = {
  household_id: string;
  person_id: string;
  calculation_mode: 'manual' | 'ballpark';
  claiming_date: string;
  current_covered_earnings?: string;
  completed_work_years?: number;
  expected_work_end_date?: string;
  earnings_pattern?: 'lower' | 'steady' | 'rising';
  manual_monthly_benefit?: string;
  cola_rate: string;
  deposit_account_id?: string;
};

export type ProjectionTransfer = {
  id: string;
  household_id: string;
  scenario_id: string;
  name: string;
  from_account_id: string;
  to_account_id: string;
  annual_amount: string;
  start_date: string;
  end_date: string | null;
  growth_rate: string | null;
  created_at: string;
  updated_at: string;
};

export type SpendingItem = {
  id: string;
  household_id: string;
  scenario_id: string;
  name: string;
  category: string;
  annual_amount: string;
  retirement_annual_amount: string | null;
  growth_rate: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectionSettings = {
  id: string;
  household_id: string;
  scenario_id: string;
  annual_spending: string | null;
  spending_mode: 'manual' | 'itemized';
  spending_inflation_rate: string | null;
  retirement_date: string | null;
  retirement_annual_spending: string | null;
  spending_account_id: string | null;
  tax_account_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectionScenario = {
  id: string;
  household_id: string;
  name: string;
  description: string | null;
  is_baseline: boolean;
  created_from_scenario_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectionScenarioAccountAssumption = {
  id: string;
  scenario_id: string;
  household_id: string;
  account_id: string;
  expected_annual_yield: string | null;
  liquidation_expense_rate: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectionScenarioPropertyAssumption = {
  id: string;
  scenario_id: string;
  household_id: string;
  property_account_id: string;
  expected_appreciation_rate: string | null;
  rent_growth_rate: string | null;
  vacancy_rate: string | null;
  created_at: string;
  updated_at: string;
};

export type AnnualTaxRecord = {
  id: string;
  household_id: string;
  tax_year: number;
  gross_income: string | null;
  total_taxes_paid: string;
  refund_or_amount_due: string | null;
  effective_tax_rate: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type NetWorthProjection = {
  household_id: string;
  scenario_id: string;
  scenario_name: string;
  start_year: number;
  end_year: number;
  interval: 'annual' | 'quarterly' | 'monthly';
  spending_mode: 'manual' | 'itemized';
  retirement_date: string | null;
  first_retirement_withdrawal_date: string | null;
  first_unfunded_date: string | null;
  warnings: string[];
  points: Array<{
    year: number;
    as_of_date: string;
    net_worth: string;
    assets_total: string;
    liabilities_total: string;
    projected_income: string;
    projected_rental_income: string;
    projected_rental_expenses: string;
    projected_taxes: string;
    projected_spending: string;
    projected_owner_property_spending: string;
    projected_mortgage_spending: string;
    projected_spending_breakdown: Array<{
      name: string;
      category: string;
      amount: string;
    }>;
    projected_liquidation_expenses: string;
    projected_unfunded_cash_flow: string;
    net_cash_flow: string;
    retirement_phase: boolean;
    cash_flows: Array<{
      account_id: string;
      account_name: string;
      cash_flow_type: string;
      amount: string;
    }>;
    accounts: Array<{
      account_id: string;
      name: string;
      account_kind: string;
      category: string;
      liquidity_class: string;
      projected_balance: string;
    }>;
  }>;
  property_sale_optimization?: {
    mode: string;
    candidate_month: number;
    candidate_day: number;
    schedules_evaluated: number;
    first_retirement_withdrawal_date: string | null;
    selected_sales: Array<{
      property_account_id: string;
      property_name: string;
      sale_date: string | null;
    }>;
  } | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>('/auth/status');
}

export function register(payload: {
  display_name: string;
  email: string;
  password: string;
}): Promise<User> {
  return request<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function login(payload: { email: string; password: string }): Promise<User> {
  return request<User>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' });
}

export function listUsers(signal?: AbortSignal): Promise<User[]> {
  return request<User[]>('/users', { signal });
}

export function getCapabilities(signal?: AbortSignal): Promise<Capabilities> {
  return request<Capabilities>('/capabilities', { signal });
}

export function createUser(payload: { display_name: string; email?: string }): Promise<User> {
  return request<User>('/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listHouseholds(userId?: string): Promise<Household[]> {
  const query = userId ? `?user_id=${userId}` : '';
  return request<Household[]>(`/households${query}`);
}

export function createHousehold(name: string, ownerUserId?: string): Promise<Household> {
  return request<Household>('/households', {
    method: 'POST',
    body: JSON.stringify({ name, owner_user_id: ownerUserId || null }),
  });
}

export function listProjectionScenarios(
  householdId: string,
  signal?: AbortSignal,
): Promise<ProjectionScenario[]> {
  return request<ProjectionScenario[]>(`/households/${householdId}/projection-scenarios`, { signal });
}

export function createProjectionScenario(
  householdId: string,
  payload: { name: string; description?: string; source_scenario_id?: string },
): Promise<ProjectionScenario> {
  return request<ProjectionScenario>(`/households/${householdId}/projection-scenarios`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function duplicateProjectionScenario(
  scenarioId: string,
  payload: { name: string; description?: string },
): Promise<ProjectionScenario> {
  return request<ProjectionScenario>(`/projection-scenarios/${scenarioId}/duplicate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateProjectionScenario(
  scenarioId: string,
  payload: { name?: string; description?: string | null },
): Promise<ProjectionScenario> {
  return request<ProjectionScenario>(`/projection-scenarios/${scenarioId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteProjectionScenario(scenarioId: string): Promise<void> {
  return request<void>(`/projection-scenarios/${scenarioId}`, { method: 'DELETE' });
}

export function listProjectionScenarioAccountAssumptions(
  scenarioId: string,
  signal?: AbortSignal,
): Promise<ProjectionScenarioAccountAssumption[]> {
  return request<ProjectionScenarioAccountAssumption[]>(
    `/projection-scenarios/${scenarioId}/account-assumptions`,
    { signal },
  );
}

export function updateProjectionScenarioAccountAssumption(
  scenarioId: string,
  accountId: string,
  payload: { expected_annual_yield?: string | null; liquidation_expense_rate?: string | null },
): Promise<ProjectionScenarioAccountAssumption> {
  return request<ProjectionScenarioAccountAssumption>(
    `/projection-scenarios/${scenarioId}/account-assumptions/${accountId}`,
    { method: 'PUT', body: JSON.stringify(payload) },
  );
}

export function listProjectionScenarioPropertyAssumptions(
  scenarioId: string,
  signal?: AbortSignal,
): Promise<ProjectionScenarioPropertyAssumption[]> {
  return request<ProjectionScenarioPropertyAssumption[]>(
    `/projection-scenarios/${scenarioId}/property-assumptions`,
    { signal },
  );
}

export function updateProjectionScenarioPropertyAssumption(
  scenarioId: string,
  propertyAccountId: string,
  payload: {
    expected_appreciation_rate?: string | null;
    rent_growth_rate?: string | null;
    vacancy_rate?: string | null;
  },
): Promise<ProjectionScenarioPropertyAssumption> {
  return request<ProjectionScenarioPropertyAssumption>(
    `/projection-scenarios/${scenarioId}/property-assumptions/${propertyAccountId}`,
    { method: 'PUT', body: JSON.stringify(payload) },
  );
}

export function listHouseholdMembers(
  householdId: string,
  signal?: AbortSignal,
): Promise<HouseholdMembership[]> {
  return request<HouseholdMembership[]>(`/households/${householdId}/members`, { signal });
}

export function addHouseholdMember(
  householdId: string,
  payload: { user_id: string; role: string },
): Promise<HouseholdMembership> {
  return request<HouseholdMembership>(`/households/${householdId}/members`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function removeHouseholdMember(householdId: string, userId: string): Promise<void> {
  return request<void>(`/households/${householdId}/members/${userId}`, { method: 'DELETE' });
}

export function exportHousehold(householdId: string): Promise<HouseholdExport> {
  return request<HouseholdExport>(`/households/${householdId}/export`);
}

export function importFintrack(payload: {
  household_id: string;
  data_dir: string;
  currency?: string;
  dry_run?: boolean;
}): Promise<FintrackImportResult> {
  return request<FintrackImportResult>('/imports/fintrack', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listAccounts(householdId: string, signal?: AbortSignal): Promise<Account[]> {
  return request<Account[]>(`/accounts?household_id=${householdId}`, { signal });
}

export function createAccount(payload: {
  household_id: string;
  name: string;
  account_kind: 'asset' | 'liability';
  category: string;
  liquidity_class: string;
  retirement_tax_treatment?: RetirementTaxTreatment;
  expected_annual_yield?: string;
  liquidation_expense_rate?: string;
  cost_basis?: string;
  currency: string;
}): Promise<Account> {
  return request<Account>('/accounts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateAccount(
  accountId: string,
  payload: {
    name?: string;
    institution_name?: string | null;
    account_kind?: 'asset' | 'liability';
    category?: string;
    liquidity_class?: string;
    retirement_tax_treatment?: RetirementTaxTreatment | null;
    expected_annual_yield?: string | null;
    liquidation_expense_rate?: string | null;
    cost_basis?: string | null;
    currency?: string;
    is_active?: boolean;
  },
): Promise<Account> {
  return request<Account>(`/accounts/${accountId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function createSnapshot(
  accountId: string,
  payload: { as_of_date: string; balance: string; currency: string },
): Promise<unknown> {
  return request(`/accounts/${accountId}/snapshots`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createSnapshotBatch(
  householdId: string,
  payload: {
    as_of_date: string;
    currency: string;
    snapshots: Array<{ account_id: string; balance: string }>;
  },
): Promise<SnapshotBatch> {
  return request<SnapshotBatch>(`/households/${householdId}/snapshot-batch`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listHouseholdSnapshots(
  householdId: string,
  accountId?: string,
  signal?: AbortSignal,
): Promise<HouseholdSnapshot[]> {
  const params = new URLSearchParams({ limit: '100' });
  if (accountId) params.set('account_id', accountId);
  return request<HouseholdSnapshot[]>(`/households/${householdId}/snapshots?${params}`, { signal });
}

export function updateSnapshot(
  accountId: string,
  snapshotId: string,
  payload: { as_of_date?: string; balance?: string; currency?: string },
): Promise<SnapshotBatch['snapshots'][number]> {
  return request<SnapshotBatch['snapshots'][number]>(`/accounts/${accountId}/snapshots/${snapshotId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteSnapshot(accountId: string, snapshotId: string): Promise<void> {
  return request<void>(`/accounts/${accountId}/snapshots/${snapshotId}`, {
    method: 'DELETE',
  });
}

export function listHouseholdAccountEvents(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<AccountEvent[]> {
  return request<AccountEvent[]>(
    `/households/${householdId}/events?scenario_id=${scenarioId}`,
    { signal },
  );
}

export function createAccountEvent(
  accountId: string,
  payload: {
    event_date: string;
    amount: string;
    currency: string;
    event_type: string;
    description?: string;
    projection_behavior?: string;
    scenario_id?: string;
  },
): Promise<AccountEvent> {
  return request<AccountEvent>(`/accounts/${accountId}/events`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateAccountEvent(
  accountId: string,
  eventId: string,
  payload: {
    account_id?: string;
    event_date?: string;
    amount?: string;
    currency?: string;
    event_type?: string;
    description?: string | null;
    projection_behavior?: string;
    scenario_id?: string;
  },
): Promise<AccountEvent> {
  return request<AccountEvent>(`/accounts/${accountId}/events/${eventId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteAccountEvent(accountId: string, eventId: string): Promise<void> {
  return request<void>(`/accounts/${accountId}/events/${eventId}`, {
    method: 'DELETE',
  });
}

export function getNetWorth(householdId: string, signal?: AbortSignal): Promise<NetWorth> {
  return request<NetWorth>(`/dashboard/${householdId}/net-worth`, { signal });
}

export function getHistoricalTrend(
  householdId: string,
  interpolate = false,
  signal?: AbortSignal,
): Promise<NetWorthHistory> {
  return request<NetWorthHistory>(
    `/dashboard/${householdId}/historical-trend?interpolate=${interpolate ? 'true' : 'false'}`,
    { signal },
  );
}

export function getNetWorthBreakdownHistory(
  householdId: string,
  signal?: AbortSignal,
): Promise<NetWorthBreakdownHistory> {
  return request<NetWorthBreakdownHistory>(`/dashboard/${householdId}/breakdown-history`, { signal });
}

export function getNetWorthHistory(householdId: string): Promise<NetWorthHistory> {
  return request<NetWorthHistory>(`/dashboard/${householdId}/net-worth/history`);
}

export function getRealEstateAnalytics(
  householdId: string,
  signal?: AbortSignal,
): Promise<RealEstateAnalytics[]> {
  return request<RealEstateAnalytics[]>(`/real-estate/analytics?household_id=${householdId}`, { signal });
}

export function listRealEstateProperties(
  householdId: string,
  signal?: AbortSignal,
): Promise<RealEstateProperty[]> {
  return request<RealEstateProperty[]>(`/real-estate/properties?household_id=${householdId}`, { signal });
}

export function createRealEstateProperty(payload: {
  account_id: string;
  property_type?: string;
  purchase_date?: string;
  purchase_price?: string;
  adjusted_tax_basis?: string;
  down_payment?: string;
  expected_appreciation_rate?: string;
  property_tax_annual?: string;
  insurance_annual?: string;
  tax_and_insurance_annual?: string;
  maintenance_rate?: string;
  hoa_monthly?: string;
  is_rental?: boolean;
  rental_start_date?: string;
  monthly_market_rent?: string;
  other_monthly_income?: string;
  rent_growth_rate?: string;
  vacancy_rate?: string;
  management_fee_rate?: string;
  utilities_annual?: string;
  other_operating_expense_annual?: string;
  capital_reserve_rate?: string;
  rental_deposit_account_id?: string;
}): Promise<RealEstateProperty> {
  return request<RealEstateProperty>('/real-estate/properties', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateRealEstateProperty(
  propertyId: string,
  payload: Partial<{
    property_type: string; purchase_date: string | null; purchase_price: string | null;
    adjusted_tax_basis: string | null; down_payment: string | null;
    expected_appreciation_rate: string | null; property_tax_annual: string | null;
    insurance_annual: string | null; tax_and_insurance_annual: string | null;
    maintenance_rate: string | null; hoa_monthly: string | null;
    is_rental: boolean; rental_start_date: string | null; monthly_market_rent: string | null;
    other_monthly_income: string | null; rent_growth_rate: string | null; vacancy_rate: string | null;
    management_fee_rate: string | null; utilities_annual: string | null;
    other_operating_expense_annual: string | null; capital_reserve_rate: string | null;
    rental_deposit_account_id: string | null;
  }>,
): Promise<RealEstateProperty> {
  return request<RealEstateProperty>(`/real-estate/properties/${propertyId}`, {
    method: 'PATCH', body: JSON.stringify(payload),
  });
}

export function listRealEstateSales(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<RealEstateSale[]> {
  return request<RealEstateSale[]>(
    `/real-estate/sales?household_id=${householdId}&scenario_id=${scenarioId}`,
    { signal },
  );
}

export function createRealEstateSale(payload: {
  property_account_id: string;
  sale_date: string;
  gross_sale_price: string;
  proceeds_account_id?: string;
  selling_expense_rate?: string;
  estimated_tax_rate?: string;
}, scenarioId: string): Promise<RealEstateSale> {
  return request<RealEstateSale>(`/real-estate/sales?scenario_id=${scenarioId}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteRealEstateSale(saleId: string): Promise<void> {
  return request<void>(`/real-estate/sales/${saleId}`, { method: 'DELETE' });
}

export function listRealEstateLiquidationStrategies(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<RealEstateLiquidationStrategy[]> {
  return request<RealEstateLiquidationStrategy[]>(
    `/real-estate/liquidation-strategies?household_id=${householdId}&scenario_id=${scenarioId}`,
    { signal },
  );
}

export function upsertRealEstateLiquidationStrategy(
  propertyAccountId: string,
  payload: {
    enabled: boolean;
    optimization_mode: 'liquidity_shortfall' | 'maximize_liquid_runway';
    priority: number;
    earliest_sale_date?: string;
    proceeds_account_id?: string;
    selling_expense_rate?: string;
    estimated_tax_rate: string;
  },
  scenarioId: string,
): Promise<RealEstateLiquidationStrategy> {
  return request<RealEstateLiquidationStrategy>(
    `/real-estate/liquidation-strategies/${propertyAccountId}?scenario_id=${scenarioId}`,
    { method: 'PUT', body: JSON.stringify(payload) },
  );
}

export function deleteRealEstateLiquidationStrategy(
  propertyAccountId: string,
  scenarioId: string,
): Promise<void> {
  return request<void>(
    `/real-estate/liquidation-strategies/${propertyAccountId}?scenario_id=${scenarioId}`,
    { method: 'DELETE' },
  );
}

export function listMortgageProfiles(
  householdId: string,
  signal?: AbortSignal,
): Promise<MortgageProfile[]> {
  return request<MortgageProfile[]>(`/mortgages?household_id=${householdId}`, { signal });
}

export function createMortgageProfile(payload: {
  liability_account_id: string;
  property_account_id?: string;
  original_principal: string;
  interest_rate: string;
  term_months: number;
  start_date: string;
  monthly_payment?: string;
  rate_type?: string;
}): Promise<MortgageProfile> {
  return request<MortgageProfile>('/mortgages', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listIncomeSources(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<IncomeSource[]> {
  return request<IncomeSource[]>(
    `/income-sources?household_id=${householdId}&scenario_id=${scenarioId}`,
    { signal },
  );
}

export function createIncomeSource(payload: {
  household_id: string;
  name: string;
  income_type?: string;
  amount: string;
  currency: string;
  frequency: string;
  start_date: string;
  end_date?: string;
  growth_rate?: string;
  deposit_account_id?: string;
}, scenarioId: string): Promise<IncomeSource> {
  return request<IncomeSource>(`/income-sources?scenario_id=${scenarioId}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listHouseholdPeople(
  householdId: string,
  signal?: AbortSignal,
): Promise<HouseholdPerson[]> {
  return request<HouseholdPerson[]>(`/household-people?household_id=${householdId}`, { signal });
}

export function createHouseholdPerson(payload: {
  household_id: string;
  name: string;
  date_of_birth: string;
}): Promise<HouseholdPerson> {
  return request<HouseholdPerson>('/household-people', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listSocialSecurityEstimates(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<SocialSecurityEstimate[]> {
  return request<SocialSecurityEstimate[]>(
    `/social-security-estimates?household_id=${householdId}&scenario_id=${scenarioId}`,
    { signal },
  );
}

export function createSocialSecurityEstimate(
  payload: SocialSecurityEstimateInput,
  scenarioId: string,
): Promise<SocialSecurityEstimate> {
  return request<SocialSecurityEstimate>(`/social-security-estimates?scenario_id=${scenarioId}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateSocialSecurityEstimate(
  estimateId: string,
  payload: SocialSecurityEstimateInput,
): Promise<SocialSecurityEstimate> {
  return request<SocialSecurityEstimate>(`/social-security-estimates/${estimateId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteSocialSecurityEstimate(estimateId: string): Promise<void> {
  return request<void>(`/social-security-estimates/${estimateId}`, { method: 'DELETE' });
}

export function createProjectionTransfer(payload: {
  household_id: string;
  name: string;
  from_account_id: string;
  to_account_id: string;
  annual_amount: string;
  start_date: string;
  end_date?: string;
  growth_rate?: string;
}, scenarioId: string): Promise<ProjectionTransfer> {
  return request<ProjectionTransfer>(`/projection-transfers?scenario_id=${scenarioId}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listProjectionTransfers(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<ProjectionTransfer[]> {
  return request<ProjectionTransfer[]>(
    `/projection-transfers?household_id=${householdId}&scenario_id=${scenarioId}`,
    { signal },
  );
}

export function deleteProjectionTransfer(projectionTransferId: string): Promise<void> {
  return request<void>(`/projection-transfers/${projectionTransferId}`, { method: 'DELETE' });
}

export function createSpendingItem(payload: {
  household_id: string;
  name: string;
  category: string;
  annual_amount: string;
  retirement_annual_amount?: string;
  growth_rate?: string;
}, scenarioId: string): Promise<SpendingItem> {
  return request<SpendingItem>(`/spending-items?scenario_id=${scenarioId}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listSpendingItems(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<SpendingItem[]> {
  return request<SpendingItem[]>(
    `/spending-items?household_id=${householdId}&scenario_id=${scenarioId}`,
    { signal },
  );
}

export function updateSpendingItem(
  spendingItemId: string,
  payload: {
    name?: string;
    category?: string;
    annual_amount?: string;
    retirement_annual_amount?: string | null;
    growth_rate?: string | null;
  },
): Promise<SpendingItem> {
  return request<SpendingItem>(`/spending-items/${spendingItemId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteSpendingItem(spendingItemId: string): Promise<void> {
  return request<void>(`/spending-items/${spendingItemId}`, { method: 'DELETE' });
}

export async function getProjectionSettings(
  householdId: string,
  scenarioId: string,
  signal?: AbortSignal,
): Promise<ProjectionSettings | null> {
  try {
    return await request<ProjectionSettings>(
      `/projection-settings/${householdId}?scenario_id=${scenarioId}`,
      { signal },
    );
  } catch (error) {
    if (String(error).includes('404')) return null;
    throw error;
  }
}

export function upsertProjectionSettings(
  householdId: string,
  payload: {
    annual_spending?: string;
    spending_mode?: 'manual' | 'itemized';
    spending_inflation_rate?: string;
    retirement_date?: string;
    retirement_annual_spending?: string;
    spending_account_id?: string;
    tax_account_id?: string;
  },
  scenarioId: string,
): Promise<ProjectionSettings> {
  return request<ProjectionSettings>(
    `/projection-settings/${householdId}?scenario_id=${scenarioId}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  );
}

export function listAnnualTaxRecords(
  householdId: string,
  signal?: AbortSignal,
): Promise<AnnualTaxRecord[]> {
  return request<AnnualTaxRecord[]>(`/annual-tax-records?household_id=${householdId}`, { signal });
}

export function createAnnualTaxRecord(payload: {
  household_id: string;
  tax_year: number;
  gross_income?: string;
  total_taxes_paid: string;
  refund_or_amount_due?: string;
  notes?: string;
}): Promise<AnnualTaxRecord> {
  return request<AnnualTaxRecord>('/annual-tax-records', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getNetWorthProjection(
  householdId: string,
  startYear: number,
  endYear: number,
  options: {
    annualSpending?: string;
    spendingInflationRate?: string;
    spendingAccountId?: string;
    taxAccountId?: string;
    interval?: 'annual' | 'quarterly' | 'monthly';
    scenarioId: string;
  },
): Promise<NetWorthProjection> {
  const params = new URLSearchParams({
    start_year: String(startYear),
    end_year: String(endYear),
  });
  if (options.annualSpending) params.set('annual_spending', options.annualSpending);
  if (options.spendingInflationRate) params.set('spending_inflation_rate', options.spendingInflationRate);
  if (options.spendingAccountId) params.set('spending_account_id', options.spendingAccountId);
  if (options.taxAccountId) params.set('tax_account_id', options.taxAccountId);
  if (options.interval) params.set('interval', options.interval);
  params.set('scenario_id', options.scenarioId);
  return request<NetWorthProjection>(`/dashboard/${householdId}/projection?${params.toString()}`);
}
