import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getCustomerContracts } from './customer.api';

export function useCustomerContractsQuery(customerId: string) {
  return useQuery({
    queryKey: queryKeys.customer.contracts(customerId),
    queryFn: () => getCustomerContracts(customerId),
    enabled: Boolean(customerId),
  });
}
