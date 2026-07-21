import { useState } from 'react';
import { useWorkbenchAccountsQuery } from '../domains/workbench/useWorkbenchAccountsQuery';
import { useDebouncedValue } from './useDebouncedValue';
import type { WorkbenchFilterKey } from '../domains/workbench/workbench.schema';

export function useWorkbenchFilter() {
  const [activeFilter, setActiveFilter] = useState<WorkbenchFilterKey>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebouncedValue(searchQuery, 300);
  const [selectedAccountId, setSelectedAccountId] = useState<string | undefined>(undefined);

  const accountsQuery = useWorkbenchAccountsQuery({ filter: activeFilter, search: debouncedSearch });
  const accounts = accountsQuery.data?.accounts ?? [];
  const totalCount = accountsQuery.data?.totalCount ?? 0;
  const selectedAccount = accounts.find((account) => account.id === selectedAccountId) ?? accounts[0];

  return {
    activeFilter,
    setActiveFilter,
    searchQuery,
    setSearchQuery,
    accounts,
    totalCount,
    selectedAccount,
    selectedAccountId,
    setSelectedAccountId,
    isLoading: accountsQuery.isLoading,
    isError: accountsQuery.isError,
    error: accountsQuery.error,
    refetch: accountsQuery.refetch,
  };
}
