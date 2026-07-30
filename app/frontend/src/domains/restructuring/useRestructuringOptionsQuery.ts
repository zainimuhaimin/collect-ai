import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getRestructuringOptions } from './restructuring.api';

export function useRestructuringOptionsQuery(custId: string) {
  return useQuery({
    queryKey: queryKeys.restructuring.options(custId),
    queryFn: () => getRestructuringOptions(custId),
    enabled: Boolean(custId),
  });
}
