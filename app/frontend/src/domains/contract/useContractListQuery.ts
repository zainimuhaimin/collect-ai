import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getContractList } from './contract.api';
import type { ContractFilter } from './contract.schema';

export function useContractListQuery(filter: ContractFilter, search: string, page: number, pageSize: number) {
  return useQuery({
    queryKey: queryKeys.contract.list(filter, search, page, pageSize),
    queryFn: () => getContractList(filter, search, page, pageSize),
    placeholderData: (previousData) => previousData,
  });
}
