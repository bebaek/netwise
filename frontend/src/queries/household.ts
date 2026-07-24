import { useQuery } from '@tanstack/react-query';
import {
  getHistoricalTrend,
  getNetWorth,
  getNetWorthBreakdownHistory,
  listAccounts,
  listHouseholdAccountEvents,
  listHouseholdSnapshots,
} from '../api';

export const householdQueryKeys = {
  all: (householdId: string) => ['households', householdId] as const,
  accounts: (householdId: string) => [...householdQueryKeys.all(householdId), 'accounts'] as const,
  events: (householdId: string) => [...householdQueryKeys.all(householdId), 'account-events'] as const,
  snapshotsAll: (householdId: string) => [
    ...householdQueryKeys.all(householdId),
    'snapshots',
  ] as const,
  snapshots: (householdId: string, accountId: string) => [
    ...householdQueryKeys.snapshotsAll(householdId),
    accountId || 'all',
  ] as const,
  financialSummary: (householdId: string) => [
    ...householdQueryKeys.all(householdId),
    'financial-summary',
  ] as const,
  netWorth: (householdId: string) => [...householdQueryKeys.financialSummary(householdId), 'net-worth'] as const,
  history: (householdId: string, interpolate: boolean) => [
    ...householdQueryKeys.financialSummary(householdId),
    'history',
    { interpolate },
  ] as const,
  breakdownHistory: (householdId: string) => [
    ...householdQueryKeys.financialSummary(householdId),
    'breakdown-history',
  ] as const,
};

export function useAccounts(householdId: string) {
  return useQuery({
    queryKey: householdQueryKeys.accounts(householdId),
    queryFn: ({ signal }) => listAccounts(householdId, signal),
    enabled: Boolean(householdId),
  });
}

export function useHouseholdAccountEvents(householdId: string) {
  return useQuery({
    queryKey: householdQueryKeys.events(householdId),
    queryFn: ({ signal }) => listHouseholdAccountEvents(householdId, signal),
    enabled: Boolean(householdId),
  });
}

export function useHouseholdSnapshots(householdId: string, accountId: string) {
  return useQuery({
    queryKey: householdQueryKeys.snapshots(householdId, accountId),
    queryFn: ({ signal }) => listHouseholdSnapshots(householdId, accountId || undefined, signal),
    enabled: Boolean(householdId),
  });
}

export function useHouseholdFinancialSummary(householdId: string, interpolate: boolean) {
  const netWorth = useQuery({
    queryKey: householdQueryKeys.netWorth(householdId),
    queryFn: ({ signal }) => getNetWorth(householdId, signal),
    enabled: Boolean(householdId),
  });
  const history = useQuery({
    queryKey: householdQueryKeys.history(householdId, interpolate),
    queryFn: ({ signal }) => getHistoricalTrend(householdId, interpolate, signal),
    enabled: Boolean(householdId),
  });
  const breakdownHistory = useQuery({
    queryKey: householdQueryKeys.breakdownHistory(householdId),
    queryFn: ({ signal }) => getNetWorthBreakdownHistory(householdId, signal),
    enabled: Boolean(householdId),
  });

  return { netWorth, history, breakdownHistory };
}
