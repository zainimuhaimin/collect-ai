import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getCustomerDetail } from './customer.api';

export function useCustomerDetailQuery(customerId: string) {
  return useQuery({
    queryKey: queryKeys.customer.detail(customerId),
    queryFn: () => getCustomerDetail(customerId),
  });
}
