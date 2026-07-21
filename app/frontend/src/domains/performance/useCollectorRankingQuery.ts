import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getCollectorRanking } from './performance.api';

export function useCollectorRankingQuery(page: number) {
  return useQuery({
    queryKey: queryKeys.performance.collectorRanking(page),
    queryFn: () => getCollectorRanking(page),
  });
}
