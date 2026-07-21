import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getModelConfig } from './aiIntelligence.api';

export function useModelConfigQuery() {
  return useQuery({
    queryKey: queryKeys.aiIntelligence.modelConfig,
    queryFn: getModelConfig,
  });
}
