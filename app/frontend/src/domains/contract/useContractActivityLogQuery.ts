import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getContractActivityLog } from './contract.api';

// Shared by Contract Detail (always fetched) and Customer Detail's per-contract expand
// (lazy — pass `enabled: false` until the row is expanded for the first time).
export function useContractActivityLogQuery(contractNo: string, options: { enabled?: boolean } = {}) {
  const { enabled = true } = options;
  return useQuery({
    queryKey: queryKeys.contract.activityLog(contractNo),
    queryFn: () => getContractActivityLog(contractNo),
    enabled: Boolean(contractNo) && enabled,
  });
}
