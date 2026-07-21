import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getPerformanceOperationalLog } from './performance.api';

export function usePerformanceOperationalLogQuery() {
  return useQuery({
    queryKey: queryKeys.performance.operationalLog,
    queryFn: getPerformanceOperationalLog,
  });
}
