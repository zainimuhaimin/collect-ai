import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getCustomerTimeline } from './customer.api';

export function useCustomerTimelineQuery(customerId: string) {
  return useQuery({
    queryKey: queryKeys.customer.timeline(customerId),
    queryFn: () => getCustomerTimeline(customerId),
  });
}
