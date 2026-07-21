import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getPerformanceFilters } from './performance.api';

export function usePerformanceFiltersQuery() {
  return useQuery({
    queryKey: queryKeys.performance.filters,
    queryFn: getPerformanceFilters,
  });
}
