import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getModelOperationalLog } from './aiIntelligence.api';

export function useModelOperationalLogQuery() {
  return useQuery({
    queryKey: queryKeys.aiIntelligence.operationalLog,
    queryFn: getModelOperationalLog,
  });
}
