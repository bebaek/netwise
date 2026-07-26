import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAccount,
  createMortgageProfile,
  createRealEstateProperty,
  createRealEstateSale,
  createSnapshot,
  deleteRealEstateLiquidationStrategy,
  deleteRealEstateSale,
  getRealEstateAnalytics,
  listMortgageProfiles,
  listRealEstateLiquidationStrategies,
  listRealEstateProperties,
  listRealEstateSales,
  updateRealEstateProperty,
  upsertRealEstateLiquidationStrategy,
  type RealEstateLiquidationStrategy,
  type RealEstateSale,
} from '../api';
import { householdQueryKeys } from './household';

export const realEstateQueryKeys = {
  all: (householdId: string) => [
    ...householdQueryKeys.all(householdId),
    'real-estate-assets',
  ] as const,
  properties: (householdId: string) => [
    ...realEstateQueryKeys.all(householdId),
    'properties',
  ] as const,
  analytics: (householdId: string) => [
    ...realEstateQueryKeys.all(householdId),
    'analytics',
  ] as const,
  mortgages: (householdId: string) => [
    ...realEstateQueryKeys.all(householdId),
    'mortgages',
  ] as const,
  planningAll: (householdId: string, scenarioId: string) => [
    ...householdQueryKeys.all(householdId),
    'planning-real-estate',
    scenarioId,
  ] as const,
  sales: (householdId: string, scenarioId: string) => [
    ...realEstateQueryKeys.planningAll(householdId, scenarioId),
    'sales',
  ] as const,
  liquidationStrategies: (householdId: string, scenarioId: string) => [
    ...realEstateQueryKeys.planningAll(householdId, scenarioId),
    'liquidation-strategies',
  ] as const,
};

type CreatePropertyVariables = {
  account: Parameters<typeof createAccount>[0];
  property: Omit<Parameters<typeof createRealEstateProperty>[0], 'account_id'>;
  snapshot?: Parameters<typeof createSnapshot>[1];
};

type UpdatePropertyVariables = {
  propertyId: string;
  payload: Parameters<typeof updateRealEstateProperty>[1];
};

type CreateMortgageVariables = {
  account: Parameters<typeof createAccount>[0];
  mortgage: Omit<Parameters<typeof createMortgageProfile>[0], 'liability_account_id'>;
  snapshot?: Parameters<typeof createSnapshot>[1];
};

type UpsertLiquidationStrategyVariables = {
  propertyAccountId: string;
  payload: Parameters<typeof upsertRealEstateLiquidationStrategy>[1];
};

export function usePlanningRealEstateData(householdId: string, scenarioId: string) {
  const sales = useQuery({
    queryKey: realEstateQueryKeys.sales(householdId, scenarioId),
    queryFn: ({ signal }) => listRealEstateSales(householdId, scenarioId, signal),
    enabled: Boolean(householdId && scenarioId),
  });
  const liquidationStrategies = useQuery({
    queryKey: realEstateQueryKeys.liquidationStrategies(householdId, scenarioId),
    queryFn: ({ signal }) => listRealEstateLiquidationStrategies(
      householdId,
      scenarioId,
      signal,
    ),
    enabled: Boolean(householdId && scenarioId),
  });

  return { sales, liquidationStrategies };
}

export function usePlanningRealEstateMutations(householdId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  const refreshSales = () => queryClient.invalidateQueries({
    queryKey: realEstateQueryKeys.sales(householdId, scenarioId),
  });
  const refreshStrategies = () => queryClient.invalidateQueries({
    queryKey: realEstateQueryKeys.liquidationStrategies(householdId, scenarioId),
  });

  const createSale = useMutation({
    mutationFn: (payload: Parameters<typeof createRealEstateSale>[0]) => (
      createRealEstateSale(payload, scenarioId)
    ),
    onSuccess: refreshSales,
  });
  const deleteSale = useMutation({
    mutationFn: (sale: RealEstateSale) => deleteRealEstateSale(sale.id),
    onSuccess: refreshSales,
  });
  const upsertLiquidationStrategy = useMutation({
    mutationFn: ({ propertyAccountId, payload }: UpsertLiquidationStrategyVariables) => (
      upsertRealEstateLiquidationStrategy(propertyAccountId, payload, scenarioId)
    ),
    onSuccess: refreshStrategies,
  });
  const deleteLiquidationStrategy = useMutation({
    mutationFn: (strategy: RealEstateLiquidationStrategy) => (
      deleteRealEstateLiquidationStrategy(strategy.property_account_id, scenarioId)
    ),
    onSuccess: refreshStrategies,
  });

  return {
    createSale,
    deleteSale,
    upsertLiquidationStrategy,
    deleteLiquidationStrategy,
    isPending: createSale.isPending
      || deleteSale.isPending
      || upsertLiquidationStrategy.isPending
      || deleteLiquidationStrategy.isPending,
  };
}

export function useRealEstateAssetData(householdId: string) {
  const properties = useQuery({
    queryKey: realEstateQueryKeys.properties(householdId),
    queryFn: ({ signal }) => listRealEstateProperties(householdId, signal),
    enabled: Boolean(householdId),
  });
  const analytics = useQuery({
    queryKey: realEstateQueryKeys.analytics(householdId),
    queryFn: ({ signal }) => getRealEstateAnalytics(householdId, signal),
    enabled: Boolean(householdId),
  });
  const mortgages = useQuery({
    queryKey: realEstateQueryKeys.mortgages(householdId),
    queryFn: ({ signal }) => listMortgageProfiles(householdId, signal),
    enabled: Boolean(householdId),
  });

  return { properties, analytics, mortgages };
}

export function useRealEstateAssetMutations(householdId: string) {
  const queryClient = useQueryClient();
  const invalidate = (...queryKeys: ReadonlyArray<readonly unknown[]>) => Promise.all(
    queryKeys.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  );

  const createProperty = useMutation({
    mutationFn: async ({ account, property, snapshot }: CreatePropertyVariables) => {
      const propertyAccount = await createAccount(account);
      await createRealEstateProperty({ ...property, account_id: propertyAccount.id });
      if (snapshot) await createSnapshot(propertyAccount.id, snapshot);
      return propertyAccount;
    },
    onSuccess: () => invalidate(
      householdQueryKeys.accounts(householdId),
      householdQueryKeys.snapshotsAll(householdId),
      householdQueryKeys.financialSummary(householdId),
      realEstateQueryKeys.properties(householdId),
      realEstateQueryKeys.analytics(householdId),
    ),
  });

  const updateProperty = useMutation({
    mutationFn: ({ propertyId, payload }: UpdatePropertyVariables) => (
      updateRealEstateProperty(propertyId, payload)
    ),
    onSuccess: () => invalidate(
      realEstateQueryKeys.properties(householdId),
      realEstateQueryKeys.analytics(householdId),
    ),
  });

  const createMortgage = useMutation({
    mutationFn: async ({ account, mortgage, snapshot }: CreateMortgageVariables) => {
      const liabilityAccount = await createAccount(account);
      await createMortgageProfile({ ...mortgage, liability_account_id: liabilityAccount.id });
      if (snapshot) await createSnapshot(liabilityAccount.id, snapshot);
      return liabilityAccount;
    },
    onSuccess: () => invalidate(
      householdQueryKeys.accounts(householdId),
      householdQueryKeys.snapshotsAll(householdId),
      householdQueryKeys.financialSummary(householdId),
      realEstateQueryKeys.analytics(householdId),
      realEstateQueryKeys.mortgages(householdId),
    ),
  });

  return {
    createProperty,
    updateProperty,
    createMortgage,
    refreshAnalytics: () => invalidate(realEstateQueryKeys.analytics(householdId)),
    isPending: createProperty.isPending || updateProperty.isPending || createMortgage.isPending,
  };
}
