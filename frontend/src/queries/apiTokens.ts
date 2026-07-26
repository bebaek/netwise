import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createApiToken,
  listApiTokenAuditEvents,
  listApiTokens,
  revokeApiToken,
} from '../api';

export const apiTokenQueryKeys = {
  all: ['api-tokens'] as const,
  auditEvents: (householdId: string) => [
    ...apiTokenQueryKeys.all,
    'audit-events',
    householdId,
  ] as const,
};

export function useApiTokens() {
  return useQuery({
    queryKey: apiTokenQueryKeys.all,
    queryFn: ({ signal }) => listApiTokens(signal),
  });
}

export function useApiTokenAuditEvents(householdId: string) {
  return useQuery({
    queryKey: apiTokenQueryKeys.auditEvents(householdId),
    queryFn: ({ signal }) => listApiTokenAuditEvents(householdId, signal),
  });
}

export function useApiTokenMutations() {
  const queryClient = useQueryClient();
  const createToken = useMutation({
    mutationFn: createApiToken,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: apiTokenQueryKeys.all }),
  });
  const revokeToken = useMutation({
    mutationFn: revokeApiToken,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: apiTokenQueryKeys.all }),
  });

  return {
    createToken,
    revokeToken,
    isPending: createToken.isPending || revokeToken.isPending,
  };
}
