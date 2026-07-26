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
  scenario: (householdId: string, scenarioId: string) => [
    ...planningQueryKeys.all(householdId),
    'scenario',
    scenarioId,
  ] as const,
  spendingItems: (householdId: string, scenarioId: string) => [
    ...planningQueryKeys.scenario(householdId, scenarioId),
    'spending-items',
  ] as const,
  taxRecords: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'annual-tax-records',
  ] as const,
  incomeSources: (householdId: string, scenarioId: string) => [
    ...planningQueryKeys.scenario(householdId, scenarioId),
    'income-sources',
  ] as const,
  householdPeople: (householdId: string) => [
    ...planningQueryKeys.all(householdId),
    'household-people',
  ] as const,
  socialSecurityEstimates: (householdId: string, scenarioId: string) => [
    ...planningQueryKeys.scenario(householdId, scenarioId),
    'social-security-estimates',
  ] as const,
  projectionTransfers: (householdId: string, scenarioId: string) => [
    ...planningQueryKeys.scenario(householdId, scenarioId),
    'projection-transfers',
  ] as const,
  projectionSettings: (householdId: string, scenarioId: string) => [
    ...planningQueryKeys.scenario(householdId, scenarioId),
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

export function usePlanningProjectionData(householdId: string, scenarioId: string) {
  const projectionTransfers = useQuery({
    queryKey: planningQueryKeys.projectionTransfers(householdId, scenarioId),
    queryFn: ({ signal }) => listProjectionTransfers(householdId, scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });
  const projectionSettings = useQuery({
    queryKey: planningQueryKeys.projectionSettings(householdId, scenarioId),
    queryFn: ({ signal }) => getProjectionSettings(householdId, scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });

  return { projectionTransfers, projectionSettings };
}

export function usePlanningProjectionMutations(householdId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  const refreshProjectionTransfers = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.projectionTransfers(householdId, scenarioId),
  });

  const createTransfer = useMutation({
    mutationFn: (payload: Parameters<typeof createProjectionTransfer>[0]) => (
      createProjectionTransfer(payload, scenarioId)
    ),
    onSuccess: refreshProjectionTransfers,
  });
  const deleteTransfer = useMutation({
    mutationFn: (transfer: ProjectionTransfer) => deleteProjectionTransfer(transfer.id),
    onSuccess: refreshProjectionTransfers,
  });
  const saveSettings = useMutation({
    mutationFn: (payload: Parameters<typeof upsertProjectionSettings>[1]) => (
      upsertProjectionSettings(householdId, payload, scenarioId)
    ),
    onSuccess: (settings) => queryClient.setQueryData(
      planningQueryKeys.projectionSettings(householdId, scenarioId),
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

export function usePlanningPeopleData(householdId: string, scenarioId: string) {
  const incomeSources = useQuery({
    queryKey: planningQueryKeys.incomeSources(householdId, scenarioId),
    queryFn: ({ signal }) => listIncomeSources(householdId, scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });
  const householdPeople = useQuery({
    queryKey: planningQueryKeys.householdPeople(householdId),
    queryFn: ({ signal }) => listHouseholdPeople(householdId, signal),
    enabled: Boolean(householdId),
  });
  const socialSecurityEstimates = useQuery({
    queryKey: planningQueryKeys.socialSecurityEstimates(householdId, scenarioId),
    queryFn: ({ signal }) => listSocialSecurityEstimates(householdId, scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });

  return { incomeSources, householdPeople, socialSecurityEstimates };
}

export function usePlanningPeopleMutations(householdId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  const refreshIncomeSources = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.incomeSources(householdId, scenarioId),
  });
  const refreshHouseholdPeople = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.householdPeople(householdId),
  });
  const refreshSocialSecurity = () => Promise.all([
    refreshIncomeSources(),
    queryClient.invalidateQueries({
      queryKey: planningQueryKeys.socialSecurityEstimates(householdId, scenarioId),
    }),
  ]);

  const createIncome = useMutation({
    mutationFn: (payload: Parameters<typeof createIncomeSource>[0]) => (
      createIncomeSource(payload, scenarioId)
    ),
    onSuccess: refreshIncomeSources,
  });
  const createPerson = useMutation({
    mutationFn: createHouseholdPerson,
    onSuccess: refreshHouseholdPeople,
  });
  const createSocialSecurity = useMutation({
    mutationFn: (payload: Parameters<typeof createSocialSecurityEstimate>[0]) => (
      createSocialSecurityEstimate(payload, scenarioId)
    ),
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

export function usePlanningBudgetData(householdId: string, scenarioId: string) {
  const spendingItems = useQuery({
    queryKey: planningQueryKeys.spendingItems(householdId, scenarioId),
    queryFn: ({ signal }) => listSpendingItems(householdId, scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });
  const taxRecords = useQuery({
    queryKey: planningQueryKeys.taxRecords(householdId),
    queryFn: ({ signal }) => listAnnualTaxRecords(householdId, signal),
    enabled: Boolean(householdId),
  });

  return { spendingItems, taxRecords };
}

export function usePlanningBudgetMutations(householdId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  const refreshSpendingItems = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.spendingItems(householdId, scenarioId),
  });
  const refreshTaxRecords = () => queryClient.invalidateQueries({
    queryKey: planningQueryKeys.taxRecords(householdId),
  });

  const createSpending = useMutation({
    mutationFn: (payload: Parameters<typeof createSpendingItem>[0]) => (
      createSpendingItem(payload, scenarioId)
    ),
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
