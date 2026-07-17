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

export type Account = {
  id: string;
  household_id: string;
  name: string;
  institution_name: string | null;
  account_kind: 'asset' | 'liability';
  category: string;
  liquidity_class: string;
  expected_annual_yield: string | null;
  liquidation_expense_rate: string | null;
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
  down_payment: string | null;
  expected_appreciation_rate: string | null;
  property_tax_annual: string | null;
  insurance_annual: string | null;
  maintenance_rate: string | null;
  hoa_monthly: string | null;
  created_at: string;
  updated_at: string;
};

export type RealEstateSale = {
  id: string;
  household_id: string;
  property_account_id: string;
  sale_date: string;
  gross_sale_price: string;
  proceeds_account_id: string;
  selling_expense_rate: string | null;
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

export type ProjectionSettings = {
  id: string;
  household_id: string;
  annual_spending: string | null;
  spending_inflation_rate: string | null;
  spending_account_id: string | null;
  tax_account_id: string | null;
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
  start_year: number;
  end_year: number;
  points: Array<{
    year: number;
    as_of_date: string;
    net_worth: string;
    assets_total: string;
    liabilities_total: string;
    projected_income: string;
    projected_taxes: string;
    projected_spending: string;
    projected_liquidation_expenses: string;
    net_cash_flow: string;
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
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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

export function listUsers(): Promise<User[]> {
  return request<User[]>('/users');
}

export function getCapabilities(): Promise<Capabilities> {
  return request<Capabilities>('/capabilities');
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

export function listHouseholdMembers(householdId: string): Promise<HouseholdMembership[]> {
  return request<HouseholdMembership[]>(`/households/${householdId}/members`);
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

export function listAccounts(householdId: string): Promise<Account[]> {
  return request<Account[]>(`/accounts?household_id=${householdId}`);
}

export function createAccount(payload: {
  household_id: string;
  name: string;
  account_kind: 'asset' | 'liability';
  category: string;
  liquidity_class: string;
  expected_annual_yield?: string;
  liquidation_expense_rate?: string;
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
    expected_annual_yield?: string | null;
    liquidation_expense_rate?: string | null;
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
): Promise<HouseholdSnapshot[]> {
  const params = new URLSearchParams({ limit: '100' });
  if (accountId) params.set('account_id', accountId);
  return request<HouseholdSnapshot[]>(`/households/${householdId}/snapshots?${params}`);
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

export function listAccountEvents(accountId: string): Promise<AccountEvent[]> {
  return request<AccountEvent[]>(`/accounts/${accountId}/events`);
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

export function getNetWorth(householdId: string): Promise<NetWorth> {
  return request<NetWorth>(`/dashboard/${householdId}/net-worth`);
}

export function getHistoricalTrend(
  householdId: string,
  interpolate = false,
): Promise<NetWorthHistory> {
  return request<NetWorthHistory>(
    `/dashboard/${householdId}/historical-trend?interpolate=${interpolate ? 'true' : 'false'}`,
  );
}

export function getNetWorthBreakdownHistory(householdId: string): Promise<NetWorthBreakdownHistory> {
  return request<NetWorthBreakdownHistory>(`/dashboard/${householdId}/breakdown-history`);
}

export function getNetWorthHistory(householdId: string): Promise<NetWorthHistory> {
  return request<NetWorthHistory>(`/dashboard/${householdId}/net-worth/history`);
}

export function listRealEstateProperties(householdId: string): Promise<RealEstateProperty[]> {
  return request<RealEstateProperty[]>(`/real-estate/properties?household_id=${householdId}`);
}

export function createRealEstateProperty(payload: {
  account_id: string;
  property_type?: string;
  purchase_date?: string;
  purchase_price?: string;
  down_payment?: string;
  expected_appreciation_rate?: string;
  property_tax_annual?: string;
  insurance_annual?: string;
  maintenance_rate?: string;
  hoa_monthly?: string;
}): Promise<RealEstateProperty> {
  return request<RealEstateProperty>('/real-estate/properties', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listRealEstateSales(householdId: string): Promise<RealEstateSale[]> {
  return request<RealEstateSale[]>(`/real-estate/sales?household_id=${householdId}`);
}

export function createRealEstateSale(payload: {
  property_account_id: string;
  sale_date: string;
  gross_sale_price: string;
  proceeds_account_id?: string;
  selling_expense_rate?: string;
}): Promise<RealEstateSale> {
  return request<RealEstateSale>('/real-estate/sales', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteRealEstateSale(saleId: string): Promise<void> {
  return request<void>(`/real-estate/sales/${saleId}`, { method: 'DELETE' });
}

export function listMortgageProfiles(householdId: string): Promise<MortgageProfile[]> {
  return request<MortgageProfile[]>(`/mortgages?household_id=${householdId}`);
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

export function listIncomeSources(householdId: string): Promise<IncomeSource[]> {
  return request<IncomeSource[]>(`/income-sources?household_id=${householdId}`);
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
}): Promise<IncomeSource> {
  return request<IncomeSource>('/income-sources', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getProjectionSettings(householdId: string): Promise<ProjectionSettings | null> {
  try {
    return await request<ProjectionSettings>(`/projection-settings/${householdId}`);
  } catch (error) {
    if (String(error).includes('404')) return null;
    throw error;
  }
}

export function upsertProjectionSettings(
  householdId: string,
  payload: {
    annual_spending?: string;
    spending_inflation_rate?: string;
    spending_account_id?: string;
    tax_account_id?: string;
  },
): Promise<ProjectionSettings> {
  return request<ProjectionSettings>(`/projection-settings/${householdId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function listAnnualTaxRecords(householdId: string): Promise<AnnualTaxRecord[]> {
  return request<AnnualTaxRecord[]>(`/annual-tax-records?household_id=${householdId}`);
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
  } = {},
): Promise<NetWorthProjection> {
  const params = new URLSearchParams({
    start_year: String(startYear),
    end_year: String(endYear),
  });
  if (options.annualSpending) params.set('annual_spending', options.annualSpending);
  if (options.spendingInflationRate) params.set('spending_inflation_rate', options.spendingInflationRate);
  if (options.spendingAccountId) params.set('spending_account_id', options.spendingAccountId);
  if (options.taxAccountId) params.set('tax_account_id', options.taxAccountId);
  return request<NetWorthProjection>(`/dashboard/${householdId}/projection?${params.toString()}`);
}
