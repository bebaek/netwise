import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAnnualTaxRecord,
  createSpendingItem,
  deleteSpendingItem,
  listAnnualTaxRecords,
  listSpendingItems,
  updateSpendingItem,
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
};

type UpdateSpendingItemVariables = {
  spendingItemId: string;
  payload: Parameters<typeof updateSpendingItem>[1];
};

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
