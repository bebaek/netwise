export type Household = {
  id: string;
  name: string;
};

export type Account = {
  id: string;
  household_id: string;
  name: string;
  institution_name: string | null;
  account_kind: 'asset' | 'liability';
  category: string;
  liquidity_class: string;
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
  }>;
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

export type AnnualExpenseEstimate = {
  household_id: string;
  tax_year: number;
  period_start: string;
  period_end: string;
  gross_income: string;
  taxes_paid: string;
  net_worth_start: string;
  net_worth_end: string;
  net_worth_change: string;
  adjustment_total: string;
  estimated_living_expense: string;
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
  return response.json() as Promise<T>;
}

export function listHouseholds(): Promise<Household[]> {
  return request<Household[]>('/households');
}

export function createHousehold(name: string): Promise<Household> {
  return request<Household>('/households', {
    method: 'POST',
    body: JSON.stringify({ name }),
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
  currency: string;
}): Promise<Account> {
  return request<Account>('/accounts', {
    method: 'POST',
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

export function getNetWorth(householdId: string): Promise<NetWorth> {
  return request<NetWorth>(`/dashboard/${householdId}/net-worth`);
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
}): Promise<IncomeSource> {
  return request<IncomeSource>('/income-sources', {
    method: 'POST',
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

export function getAnnualExpenseEstimate(
  householdId: string,
  taxYear: number,
): Promise<AnnualExpenseEstimate> {
  return request<AnnualExpenseEstimate>(`/dashboard/${householdId}/expense-estimates/${taxYear}`);
}
