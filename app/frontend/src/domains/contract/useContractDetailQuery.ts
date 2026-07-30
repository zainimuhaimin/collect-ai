import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getContractDetail } from './contract.api';

export function useContractDetailQuery(contractNo: string) {
  return useQuery({
    queryKey: queryKeys.contract.detail(contractNo),
    queryFn: () => getContractDetail(contractNo),
    enabled: Boolean(contractNo),
  });
}
