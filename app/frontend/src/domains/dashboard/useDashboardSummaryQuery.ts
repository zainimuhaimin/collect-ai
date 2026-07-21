import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getDashboardSummary } from './dashboard.api';

export function useDashboardSummaryQuery() {
  return useQuery({
    queryKey: queryKeys.dashboard.summary,
    queryFn: getDashboardSummary,
  });
}
