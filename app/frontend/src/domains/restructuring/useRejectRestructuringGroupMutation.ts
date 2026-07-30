import { useMutation, useQueryClient } from '@tanstack/react-query';
import { rejectRestructuringGroup } from './restructuring.api';

export function useRejectRestructuringGroupMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (groupId: string) => rejectRestructuringGroup(groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['restructuring', 'groups'] });
    },
  });
}
