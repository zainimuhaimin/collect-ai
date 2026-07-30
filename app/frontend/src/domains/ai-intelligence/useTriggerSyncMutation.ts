import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { triggerSync } from './aiIntelligence.api';

export function useTriggerSyncMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: triggerSync,
    onSettled: () => {
      // Whether it started fresh (202) or was already running (409, handled by the
      // caller), refetch status immediately so polling picks up the current step.
      queryClient.invalidateQueries({ queryKey: queryKeys.aiIntelligence.syncStatus });
    },
  });
}
