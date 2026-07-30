import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getCustomerList } from './customer.api';
import type { CustomerFilter } from './customer.schema';

export function useCustomerListQuery(filter: CustomerFilter, search: string, page: number, pageSize: number) {
  return useQuery({
    queryKey: queryKeys.customer.list(filter, search, page, pageSize),
    queryFn: () => getCustomerList(filter, search, page, pageSize),
    placeholderData: (previousData) => previousData,
  });
}
