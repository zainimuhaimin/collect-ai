import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getRestructuringGroupDetail } from './restructuring.api';

export function useRestructuringGroupDetailQuery(groupId: string) {
  return useQuery({
    queryKey: queryKeys.restructuring.groupDetail(groupId),
    queryFn: () => getRestructuringGroupDetail(groupId),
    enabled: groupId.length > 0,
  });
}
