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
