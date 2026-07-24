import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAnnualTaxRecord,
  createHouseholdPerson,
  createIncomeSource,
  createProjectionTransfer,
  createSocialSecurityEstimate,
  createSpendingItem,
  deleteSocialSecurityEstimate,
  deleteProjectionTransfer,
  deleteSpendingItem,
  getProjectionSettings,
  listAnnualTaxRecords,
  listHouseholdPeople,
  listIncomeSources,
  listProjectionTransfers,
  listSocialSecurityEstimates,
  listSpendingItems,
  updateSocialSecurityEstimate,
  updateSpendingItem,
  upsertProjectionSettings,
  type ProjectionTransfer,
  type SocialSecurityEstimate,
  type SpendingItem,
} from '../api';
import { householdQueryKeys } from './household';

export const planningQueryKeys = {
  all: (householdId: string) => [
    ...householdQueryKeys.all(householdId),
    'planning',
  ] as const,
  spendingItems: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'spending-items',
  ] as const,
  taxRecords: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'annual-tax-records',
  ] as const,
  incomeSources: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'income-sources',
  ] as const,
  householdPeople: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'household-people',
  ] as const,
  socialSecurityEstimates: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'social-security-estimates',
  ] as const,
  projectionTransfers: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'projection-transfers',
  ] as const,
  projectionSettings: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'projection-settings',
  ] as const,
};

type UpdateSpendingItemVariables = {
  spendingItemId: string;
  payload: Parameters<typeof updateSpendingItem>[1];
};

type UpdateSocialSecurityEstimateVariables = {
  estimateId: string;
  payload: Parameters<typeof updateSocialSecurityEstimate>[1];
};

export function usePlanningProjectionData(householdId: string) {
  const projectionTransfers = useQuery({
    queryKey: planningQueryKeys.projectionTransfers(householdId),
    queryFn: ({ signal }) => listProjectionTransfers(householdId, signal),
    enabled: Boolean(householdId),
  });
  const projectionSettings = useQuery({
    queryKey: planningQueryKeys.projectionSettings(householdId),
    queryFn: ({ signal }) => getProjectionSettings(householdId, signal),
    enabled: Boolean(householdId),
  });

  return { projectionTransfers, projectionSettings };
}

export function usePlanningProjectionMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refreshProjectionTransfers = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.projectionTransfers(householdId),
  });

  const createTransfer = useMutation({
    mutationFn: createProjectionTransfer,
    onSuccess: refreshProjectionTransfers,
  });
  const deleteTransfer = useMutation({
    mutationFn: (transfer: ProjectionTransfer) => deleteProjectionTransfer(transfer.id),
    onSuccess: refreshProjectionTransfers,
  });
  const saveSettings = useMutation({
    mutationFn: (payload: Parameters<typeof upsertProjectionSettings>[1]) => (
      upsertProjectionSettings(householdId, payload)
    ),
    onSuccess: (settings) => queryClient.setQueryData(
      planningQueryKeys.projectionSettings(householdId),
      settings,
    ),
  });

  return {
    createTransfer,
    deleteTransfer,
    saveSettings,
    isPending: createTransfer.isPending || deleteTransfer.isPending || saveSettings.isPending,
  };
}

export function usePlanningPeopleData(householdId: string) {
  const incomeSources = useQuery({
    queryKey: planningQueryKeys.incomeSources(householdId),
    queryFn: ({ signal }) => listIncomeSources(householdId, signal),
    enabled: Boolean(householdId),
  });
  const householdPeople = useQuery({
    queryKey: planningQueryKeys.householdPeople(householdId),
    queryFn: ({ signal }) => listHouseholdPeople(householdId, signal),
    enabled: Boolean(householdId),
  });
  const socialSecurityEstimates = useQuery({
    queryKey: planningQueryKeys.socialSecurityEstimates(householdId),
    queryFn: ({ signal }) => listSocialSecurityEstimates(householdId, signal),
    enabled: Boolean(householdId),
  });

  return { incomeSources, householdPeople, socialSecurityEstimates };
}

export function usePlanningPeopleMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refreshIncomeSources = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.incomeSources(householdId),
  });
  const refreshHouseholdPeople = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.householdPeople(householdId),
  });
  const refreshSocialSecurity = () => Promise.all([
    refreshIncomeSources(),
    queryClient.invalidateQueries({
      queryKey: planningQueryKeys.socialSecurityEstimates(householdId),
    }),
  ]);

  const createIncome = useMutation({
    mutationFn: createIncomeSource,
    onSuccess: refreshIncomeSources,
  });
  const createPerson = useMutation({
    mutationFn: createHouseholdPerson,
    onSuccess: refreshHouseholdPeople,
  });
  const createSocialSecurity = useMutation({
    mutationFn: createSocialSecurityEstimate,
    onSuccess: refreshSocialSecurity,
  });
  const updateSocialSecurity = useMutation({
    mutationFn: ({ estimateId, payload }: UpdateSocialSecurityEstimateVariables) => (
      updateSocialSecurityEstimate(estimateId, payload)
    ),
    onSuccess: refreshSocialSecurity,
  });
  const deleteSocialSecurity = useMutation({
    mutationFn: (estimate: SocialSecurityEstimate) => deleteSocialSecurityEstimate(estimate.id),
    onSuccess: refreshSocialSecurity,
  });

  return {
    createIncome,
    createPerson,
    createSocialSecurity,
    updateSocialSecurity,
    deleteSocialSecurity,
    isPending: createIncome.isPending
      || createPerson.isPending
      || createSocialSecurity.isPending
      || updateSocialSecurity.isPending
      || deleteSocialSecurity.isPending,
  };
}

export function usePlanningBudgetData(householdId: string) {
  const spendingItems = useQuery({
    queryKey: planningQueryKeys.spendingItems(householdId),
    queryFn: ({ signal }) => listSpendingItems(householdId, signal),
    enabled: Boolean(householdId),
  });
  const taxRecords = useQuery({
    queryKey: planningQueryKeys.taxRecords(householdId),
    queryFn: ({ signal }) => listAnnualTaxRecords(householdId, signal),
    enabled: Boolean(householdId),
  });

  return { spendingItems, taxRecords };
}

export function usePlanningBudgetMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refreshSpendingItems = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.spendingItems(householdId),
  });
  const refreshTaxRecords = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.taxRecords(householdId),
  });

  const createSpending = useMutation({
    mutationFn: createSpendingItem,
    onSuccess: refreshSpendingItems,
  });
  const updateSpending = useMutation({
    mutationFn: ({ spendingItemId, payload }: UpdateSpendingItemVariables) => (
      updateSpendingItem(spendingItemId, payload)
    ),
    onSuccess: refreshSpendingItems,
  });
  const deleteSpending = useMutation({
    mutationFn: (spendingItem: SpendingItem) => deleteSpendingItem(spendingItem.id),
    onSuccess: refreshSpendingItems,
  });
  const createTaxRecord = useMutation({
    mutationFn: createAnnualTaxRecord,
    onSuccess: refreshTaxRecords,
  });

  return {
    createSpending,
    updateSpending,
    deleteSpending,
    createTaxRecord,
    isPending: createSpending.isPending
      || updateSpending.isPending
      || deleteSpending.isPending
      || createTaxRecord.isPending,
  };
}
