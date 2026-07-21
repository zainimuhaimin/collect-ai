import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { saveWeightingParameters } from './aiIntelligence.api';

export function useSaveWeightingParametersMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: saveWeightingParameters,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.aiIntelligence.modelConfig });
      queryClient.invalidateQueries({ queryKey: queryKeys.aiIntelligence.operationalLog });
    },
  });
}
