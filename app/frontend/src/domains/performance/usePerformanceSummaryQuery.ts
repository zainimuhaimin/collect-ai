import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getPerformanceSummary } from './performance.api';

export function usePerformanceSummaryQuery() {
  return useQuery({
    queryKey: queryKeys.performance.summary,
    queryFn: getPerformanceSummary,
  });
}
