import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getWorkbenchActivityLog } from './workbench.api';

export function useWorkbenchActivityLogQuery() {
  return useQuery({
    queryKey: queryKeys.workbench.activityLog,
    queryFn: getWorkbenchActivityLog,
  });
}
