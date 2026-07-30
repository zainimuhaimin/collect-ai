import { useMutation, useQueryClient } from '@tanstack/react-query';
import { approveRestructuringGroup } from './restructuring.api';

export function useApproveRestructuringGroupMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (groupId: string) => approveRestructuringGroup(groupId),
    onSuccess: () => {
      // Prefix match invalidates every status tab (['restructuring', 'groups', status]).
      queryClient.invalidateQueries({ queryKey: ['restructuring', 'groups'] });
    },
  });
}
