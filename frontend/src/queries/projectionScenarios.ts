import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createProjectionScenario,
  deleteProjectionScenario,
  duplicateProjectionScenario,
  listProjectionScenarioAccountAssumptions,
  listProjectionScenarioPropertyAssumptions,
  listProjectionScenarios,
  updateProjectionScenario,
  updateProjectionScenarioAccountAssumption,
  updateProjectionScenarioPropertyAssumption,
} from '../api';
import { householdQueryKeys } from './household';

export const projectionScenarioQueryKeys = {
  list: (householdId: string) => [
    ...householdQueryKeys.all(householdId),
    'projection-scenarios',
  ] as const,
  accountAssumptions: (householdId: string, scenarioId: string) => [
    ...projectionScenarioQueryKeys.list(householdId),
    scenarioId,
    'account-assumptions',
  ] as const,
  propertyAssumptions: (householdId: string, scenarioId: string) => [
    ...projectionScenarioQueryKeys.list(householdId),
    scenarioId,
    'property-assumptions',
  ] as const,
};

export function useProjectionScenarios(householdId: string) {
  return useQuery({
    queryKey: projectionScenarioQueryKeys.list(householdId),
    queryFn: ({ signal }) => listProjectionScenarios(householdId, signal),
    enabled: Boolean(householdId),
  });
}

export function useProjectionScenarioMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({
    queryKey: projectionScenarioQueryKeys.list(householdId),
    exact: true,
  });

  const create = useMutation({
    mutationFn: (payload: { name: string; description?: string }) => (
      createProjectionScenario(householdId, payload)
    ),
    onSuccess: refresh,
  });
  const duplicate = useMutation({
    mutationFn: ({
      sourceScenarioId,
      payload,
    }: {
      sourceScenarioId: string;
      payload: { name: string; description?: string };
    }) => duplicateProjectionScenario(sourceScenarioId, payload),
    onSuccess: refresh,
  });
  const update = useMutation({
    mutationFn: ({
      scenarioId,
      payload,
    }: {
      scenarioId: string;
      payload: { name?: string; description?: string | null };
    }) => updateProjectionScenario(scenarioId, payload),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: deleteProjectionScenario,
    onSuccess: refresh,
  });

  return {
    create,
    duplicate,
    update,
    remove,
    isPending: create.isPending || duplicate.isPending || update.isPending || remove.isPending,
  };
}

export function useProjectionScenarioAssumptions(householdId: string, scenarioId: string) {
  const accountAssumptions = useQuery({
    queryKey: projectionScenarioQueryKeys.accountAssumptions(householdId, scenarioId),
    queryFn: ({ signal }) => listProjectionScenarioAccountAssumptions(scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });
  const propertyAssumptions = useQuery({
    queryKey: projectionScenarioQueryKeys.propertyAssumptions(householdId, scenarioId),
    queryFn: ({ signal }) => listProjectionScenarioPropertyAssumptions(scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });
  return { accountAssumptions, propertyAssumptions };
}

export function useProjectionScenarioAssumptionMutations(
  householdId: string,
  scenarioId: string,
) {
  const queryClient = useQueryClient();
  const updateAccount = useMutation({
    mutationFn: ({
      accountId,
      payload,
    }: {
      accountId: string;
      payload: { expected_annual_yield?: string | null; liquidation_expense_rate?: string | null };
    }) => updateProjectionScenarioAccountAssumption(scenarioId, accountId, payload),
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: projectionScenarioQueryKeys.accountAssumptions(householdId, scenarioId),
    }),
  });
  const updateProperty = useMutation({
    mutationFn: ({
      propertyAccountId,
      payload,
    }: {
      propertyAccountId: string;
      payload: {
        expected_appreciation_rate?: string | null;
        rent_growth_rate?: string | null;
        vacancy_rate?: string | null;
      };
    }) => updateProjectionScenarioPropertyAssumption(scenarioId, propertyAccountId, payload),
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: projectionScenarioQueryKeys.propertyAssumptions(householdId, scenarioId),
    }),
  });
  return {
    updateAccount,
    updateProperty,
    isPending: updateAccount.isPending || updateProperty.isPending,
  };
}
