import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createApiToken,
  listApiTokens,
  revokeApiToken,
} from '../api';

export const apiTokenQueryKeys = {
  all: ['api-tokens'] as const,
};

export function useApiTokens() {
  return useQuery({
    queryKey: apiTokenQueryKeys.all,
    queryFn: ({ signal }) => listApiTokens(signal),
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
