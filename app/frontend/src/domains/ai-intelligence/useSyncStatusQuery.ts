import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getSyncStatus } from './aiIntelligence.api';

// Polls every ~3s while a sync is running (so step-by-step progress stays fresh), and
// every ~30s otherwise (so "Terakhir di-scoring" doesn't go stale without requiring a
// page reload).
export function useSyncStatusQuery() {
  return useQuery({
    queryKey: queryKeys.aiIntelligence.syncStatus,
    queryFn: getSyncStatus,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 3_000 : 30_000),
  });
}
