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
