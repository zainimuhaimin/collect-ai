import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getRestructuringGroups } from './restructuring.api';
import type { RestructuringGroupStatusFilter } from './restructuring.schema';

export function useRestructuringGroupsQuery(
  status: RestructuringGroupStatusFilter,
  search = '',
  page = 1,
  pageSize = 10,
) {
  return useQuery({
    queryKey: queryKeys.restructuring.groups(status, search, page, pageSize),
    queryFn: () => getRestructuringGroups(status, search, page, pageSize),
    placeholderData: (previousData) => previousData,
  });
}
