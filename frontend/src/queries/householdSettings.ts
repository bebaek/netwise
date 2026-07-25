import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  addHouseholdMember,
  createUser,
  exportHousehold,
  getCapabilities,
  importFintrack,
  listUsers,
  removeHouseholdMember,
  type User,
} from '../api';
import { householdQueryKeys } from './household';

export const householdSettingsQueryKeys = {
  all: ['household-settings'] as const,
  users: () => [...householdSettingsQueryKeys.all, 'users'] as const,
  capabilities: () => [...householdSettingsQueryKeys.all, 'capabilities'] as const,
};

export function useHouseholdSettingsData() {
  const users = useQuery({
    queryKey: householdSettingsQueryKeys.users(),
    queryFn: ({ signal }) => listUsers(signal),
  });
  const capabilities = useQuery({
    queryKey: householdSettingsQueryKeys.capabilities(),
    queryFn: ({ signal }) => getCapabilities(signal),
  });

  return { users, capabilities };
}

export function useHouseholdSettingsMutations(householdId: string) {
  const queryClient = useQueryClient();
  const refreshMembers = () => queryClient.invalidateQueries({
    queryKey: householdQueryKeys.members(householdId),
  });

  const createHouseholdUser = useMutation({
    mutationFn: createUser,
    onSuccess: (user) => queryClient.setQueryData<User[]>(
      householdSettingsQueryKeys.users(),
      (current = []) => [...current.filter((item) => item.id !== user.id), user],
    ),
  });
  const addMember = useMutation({
    mutationFn: (payload: Parameters<typeof addHouseholdMember>[1]) => (
      addHouseholdMember(householdId, payload)
    ),
    onSuccess: refreshMembers,
  });
  const removeMember = useMutation({
    mutationFn: (userId: string) => removeHouseholdMember(householdId, userId),
    onSuccess: refreshMembers,
  });
  const downloadExport = useMutation({
    mutationFn: () => exportHousehold(householdId),
  });
  const importData = useMutation({
    mutationFn: importFintrack,
    onSuccess: (result) => {
      if (!result.dry_run) {
        return queryClient.invalidateQueries({ queryKey: householdQueryKeys.all(householdId) });
      }
      return undefined;
    },
  });

  return {
    createHouseholdUser,
    addMember,
    removeMember,
    downloadExport,
    importData,
    isPending: createHouseholdUser.isPending
      || addMember.isPending
      || removeMember.isPending
      || downloadExport.isPending
      || importData.isPending,
  };
}
