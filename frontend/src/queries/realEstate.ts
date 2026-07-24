import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAccount,
  createMortgageProfile,
  createRealEstateProperty,
  createSnapshot,
  getRealEstateAnalytics,
  listMortgageProfiles,
  listRealEstateProperties,
  updateRealEstateProperty,
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
