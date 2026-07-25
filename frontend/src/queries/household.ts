import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAccount,
  createAccountEvent,
  createSnapshot,
  createSnapshotBatch,
  deleteAccountEvent,
  deleteSnapshot,
  getHistoricalTrend,
  getNetWorth,
  getNetWorthBreakdownHistory,
  listAccounts,
  listHouseholdAccountEvents,
  listHouseholdMembers,
  listHouseholdSnapshots,
  updateAccount,
  updateAccountEvent,
  updateSnapshot,
  type AccountEvent,
  type HouseholdSnapshot,
} from '../api';

export const householdQueryKeys = {
  all: (householdId: string) => ['households', householdId] as const,
  accounts: (householdId: string) => [...householdQueryKeys.all(householdId), 'accounts'] as const,
  members: (householdId: string) => [...householdQueryKeys.all(householdId), 'members'] as const,
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

type UpdateAccountVariables = {
  accountId: string;
  payload: Parameters<typeof updateAccount>[1];
};

type CreateAccountEventVariables = {
  accountId: string;
  payload: Parameters<typeof createAccountEvent>[1];
};

type UpdateAccountEventVariables = {
  accountId: string;
  eventId: string;
  payload: Parameters<typeof updateAccountEvent>[2];
};

export function useAccountEventMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refreshEvents = () => queryClient.invalidateQueries({
    queryKey: householdQueryKeys.events(householdId),
  });

  const create = useMutation({
    mutationFn: ({ accountId, payload }: CreateAccountEventVariables) => (
      createAccountEvent(accountId, payload)
    ),
    onSuccess: refreshEvents,
  });
  const update = useMutation({
    mutationFn: ({ accountId, eventId, payload }: UpdateAccountEventVariables) => (
      updateAccountEvent(accountId, eventId, payload)
    ),
    onSuccess: refreshEvents,
  });
  const remove = useMutation({
    mutationFn: (event: AccountEvent) => deleteAccountEvent(event.account_id, event.id),
    onSuccess: refreshEvents,
  });

  return {
    create,
    update,
    remove,
    isPending: create.isPending || update.isPending || remove.isPending,
  };
}

export function useAccountMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refreshAccountData = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: householdQueryKeys.accounts(householdId) }),
    queryClient.invalidateQueries({ queryKey: householdQueryKeys.financialSummary(householdId) }),
  ]);

  const create = useMutation({
    mutationFn: createAccount,
    onSuccess: refreshAccountData,
  });
  const update = useMutation({
    mutationFn: ({ accountId, payload }: UpdateAccountVariables) => updateAccount(accountId, payload),
    onSuccess: refreshAccountData,
  });

  return {
    create,
    update,
    isPending: create.isPending || update.isPending,
  };
}

export function useAccounts(householdId: string) {
  return useQuery({
    queryKey: householdQueryKeys.accounts(householdId),
    queryFn: ({ signal }) => listAccounts(householdId, signal),
    enabled: Boolean(householdId),
  });
}

export function useHouseholdMembers(householdId: string) {
  return useQuery({
    queryKey: householdQueryKeys.members(householdId),
    queryFn: ({ signal }) => listHouseholdMembers(householdId, signal),
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

type CreateSnapshotVariables = {
  accountId: string;
  payload: { as_of_date: string; balance: string; currency: string };
};

type UpdateSnapshotVariables = {
  snapshot: HouseholdSnapshot;
  payload: { as_of_date: string; balance: string; currency: string };
};

export function useSnapshotMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refreshSnapshotData = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: householdQueryKeys.snapshotsAll(householdId) }),
    queryClient.invalidateQueries({ queryKey: householdQueryKeys.financialSummary(householdId) }),
  ]);

  const createOne = useMutation({
    mutationFn: ({ accountId, payload }: CreateSnapshotVariables) => createSnapshot(accountId, payload),
    onSuccess: refreshSnapshotData,
  });
  const createBatch = useMutation({
    mutationFn: (payload: {
      as_of_date: string;
      currency: string;
      snapshots: Array<{ account_id: string; balance: string }>;
    }) => createSnapshotBatch(householdId, payload),
    onSuccess: refreshSnapshotData,
  });
  const update = useMutation({
    mutationFn: ({ snapshot, payload }: UpdateSnapshotVariables) => (
      updateSnapshot(snapshot.account_id, snapshot.id, payload)
    ),
    onSuccess: refreshSnapshotData,
  });
  const remove = useMutation({
    mutationFn: (snapshot: HouseholdSnapshot) => deleteSnapshot(snapshot.account_id, snapshot.id),
    onSuccess: refreshSnapshotData,
  });

  return {
    createOne,
    createBatch,
    update,
    remove,
    isPending: createOne.isPending || createBatch.isPending || update.isPending || remove.isPending,
  };
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
