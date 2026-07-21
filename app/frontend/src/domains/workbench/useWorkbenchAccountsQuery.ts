import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getWorkbenchAccounts, type WorkbenchAccountsParams } from './workbench.api';

export function useWorkbenchAccountsQuery({ filter, search }: WorkbenchAccountsParams) {
  return useQuery({
    queryKey: queryKeys.workbench.accounts(filter, search),
    queryFn: () => getWorkbenchAccounts({ filter, search }),
  });
}
