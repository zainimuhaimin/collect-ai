import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AppLayout from '../layouts/AppLayout';
import FilterChips from '../components/FilterChips';
import Pagination from '../components/Pagination';
import Chip from '../components/Chip';
import ContractListSkeleton from '../components/skeletons/ContractListSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { usePagination } from '../hooks/usePagination';
import { useContractListQuery } from '../domains/contract/useContractListQuery';
import { RISK_SEGMENT_TONE } from '../domains/shared/riskSegment';
import type { ContractFilter } from '../domains/contract/contract.schema';

const PAGE_SIZE = 10;

const FILTER_OPTIONS: { readonly key: ContractFilter; readonly label: string }[] = [
  { key: 'all', label: 'Semua Contract' },
  { key: 'dpd_30_plus', label: 'DPD 30+' },
  { key: 'high_priority', label: 'Critical Risk' },
  { key: 'broken_ptp', label: 'Broken PTP' },
  { key: 'high_ambc', label: 'High Billing Amount' },
];

interface ContractListPageProps {
  readonly className?: string;
}

export default function ContractListPage({ className = '' }: ContractListPageProps) {
  const [filter, setFilter] = useState<ContractFilter>('all');
  const [search, setSearch] = useState('');
  const [totalPages, setTotalPages] = useState(1);
  const debouncedSearch = useDebouncedValue(search, 300);
  const pagination = usePagination(totalPages);

  const listQuery = useContractListQuery(filter, debouncedSearch, pagination.page, PAGE_SIZE);

  useEffect(() => {
    if (listQuery.data) {
      setTotalPages(listQuery.data.pageInfo.totalPages);
    }
  }, [listQuery.data]);

  useEffect(() => {
    pagination.goToPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, debouncedSearch]);

  return (
    <AppLayout title="Contract" searchPlaceholder="Search contract no, customer name or ID...">
      <div className={`space-y-6 ${className}`}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <FilterChips
            options={FILTER_OPTIONS.map((option) => option.label)}
            activeOption={FILTER_OPTIONS.find((option) => option.key === filter)?.label ?? ''}
            onSelect={(label) => {
              const found = FILTER_OPTIONS.find((option) => option.label === label);
              if (found) setFilter(found.key);
            }}
          />
          <div className="flex items-center gap-2 border border-outline-variant dark:border-outline-variant/30 rounded-lg px-3 py-2 w-full md:w-72">
            <span className="material-symbols-outlined text-on-surface-variant dark:text-surface-variant text-lg">search</span>
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Cari nomor kontrak, nama, atau ID..."
              className="bg-transparent flex-1 text-body-md text-on-surface dark:text-on-background focus:outline-none"
            />
          </div>
        </div>

        {listQuery.isLoading ? (
          <ContractListSkeleton />
        ) : listQuery.isError || !listQuery.data ? (
          <ErrorState message={toDisplayMessage(listQuery.error)} onRetry={() => listQuery.refetch()} />
        ) : (
          <>
            <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant border-b border-outline-variant dark:border-outline-variant/30">
                      <th className="py-3 pl-5 pr-4">Contract No</th>
                      <th className="py-3 pr-4">Customer</th>
                      <th className="py-3 pr-4">Product Type</th>
                      <th className="py-3 pr-4">DPD</th>
                      <th className="py-3 pr-4">Outstanding</th>
                      <th className="py-3 pr-4">Risk Segment</th>
                      <th className="py-3 pr-5">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {listQuery.data.contracts.map((contract) => (
                      <tr key={contract.contractNo} className="border-b border-outline-variant dark:border-outline-variant/20">
                        <td className="py-4 pl-5 pr-4 text-label-lg font-semibold text-on-surface dark:text-on-background">
                          {contract.contractNo}
                        </td>
                        <td className="py-4 pr-4">
                          <Link
                            to={`/customers/${contract.custId}`}
                            className="text-body-md text-primary-container dark:text-primary-fixed-dim hover:underline"
                          >
                            {contract.custName}
                          </Link>
                        </td>
                        <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{contract.productType}</td>
                        <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{contract.dpdCurrent}</td>
                        <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{contract.outstanding}</td>
                        <td className="py-4 pr-4">
                          <Chip tone={RISK_SEGMENT_TONE[contract.riskSegment]}>{contract.riskSegment}</Chip>
                        </td>
                        <td className="py-4 pr-5">
                          <Link
                            to={`/contracts/${contract.contractNo}`}
                            className="text-label-lg font-semibold text-primary-container dark:text-primary-fixed-dim hover:underline"
                          >
                            Detail
                          </Link>
                        </td>
                      </tr>
                    ))}
                    {listQuery.data.contracts.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-body-md text-on-surface-variant dark:text-surface-variant">
                          Tidak ada kontrak yang cocok dengan filter/pencarian ini.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
                Showing {listQuery.data.pageInfo.showingFrom}-{listQuery.data.pageInfo.showingTo} of{' '}
                {listQuery.data.pageInfo.totalContracts} contracts
              </p>
              <Pagination
                page={pagination.page}
                totalPages={listQuery.data.pageInfo.totalPages}
                onNext={pagination.nextPage}
                onPrevious={pagination.previousPage}
                onGoToPage={pagination.goToPage}
              />
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}
