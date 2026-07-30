import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AppLayout from '../layouts/AppLayout';
import Chip from '../components/Chip';
import Pagination from '../components/Pagination';
import RestructuringApprovalSkeleton from '../components/skeletons/RestructuringApprovalSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { usePagination } from '../hooks/usePagination';
import { useRestructuringGroupsQuery } from '../domains/restructuring/useRestructuringGroupsQuery';
import type { RestructuringGroupStatusFilter, EligibilityTier } from '../domains/restructuring/restructuring.schema';

const TIER_TONE: Record<EligibilityTier, 'success' | 'medium' | 'danger'> = {
  AUTO: 'success',
  MANUAL_REVIEW: 'medium',
  BLOCKED: 'danger',
};

const PAGE_SIZE = 10;

interface RestructuringApprovalPageProps {
  readonly className?: string;
}

export default function RestructuringApprovalPage({ className = '' }: RestructuringApprovalPageProps) {
  const [tab, setTab] = useState<RestructuringGroupStatusFilter>('GENERATED');
  const [search, setSearch] = useState('');
  const [totalPages, setTotalPages] = useState(1);
  const debouncedSearch = useDebouncedValue(search, 300);
  const pagination = usePagination(totalPages);
  const groupsQuery = useRestructuringGroupsQuery(tab, debouncedSearch, pagination.page, PAGE_SIZE);

  useEffect(() => {
    if (groupsQuery.data) {
      setTotalPages(groupsQuery.data.pageInfo.totalPages);
    }
  }, [groupsQuery.data]);

  useEffect(() => {
    pagination.goToPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, debouncedSearch]);

  return (
    <AppLayout title="Restructuring Approval" searchPlaceholder="Search group or customer ID...">
      <div className={`space-y-6 ${className}`}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setTab('GENERATED')}
              className={`px-4 py-2 rounded-lg text-label-lg font-semibold ${
                tab === 'GENERATED' ? 'bg-primary-container text-on-primary' : 'border border-outline-variant dark:border-outline-variant/30 text-on-surface-variant dark:text-surface-variant'
              }`}
            >
              Menunggu Approval
            </button>
            <button
              type="button"
              onClick={() => setTab('HISTORY')}
              className={`px-4 py-2 rounded-lg text-label-lg font-semibold ${
                tab === 'HISTORY' ? 'bg-primary-container text-on-primary' : 'border border-outline-variant dark:border-outline-variant/30 text-on-surface-variant dark:text-surface-variant'
              }`}
            >
              Riwayat
            </button>
          </div>
          <div className="flex items-center gap-2 border border-outline-variant dark:border-outline-variant/30 rounded-lg px-3 py-2 w-full md:w-72">
            <span className="material-symbols-outlined text-on-surface-variant dark:text-surface-variant text-lg">search</span>
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Cari group ID atau customer ID..."
              className="bg-transparent flex-1 text-body-md text-on-surface dark:text-on-background focus:outline-none"
            />
          </div>
        </div>

        {groupsQuery.isLoading ? (
          <RestructuringApprovalSkeleton />
        ) : groupsQuery.isError || !groupsQuery.data ? (
          <ErrorState message={toDisplayMessage(groupsQuery.error)} onRetry={() => groupsQuery.refetch()} />
        ) : (
          <>
            <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant border-b border-outline-variant dark:border-outline-variant/30">
                      <th className="py-3 pl-5 pr-4">Group ID</th>
                      <th className="py-3 pr-4">Customer</th>
                      <th className="py-3 pr-4">Offer Type</th>
                      {/* Kept visible on BOTH tabs on purpose, even though it always
                          reads MANUAL_REVIEW on the pending-queue tab — AUTO-eligible
                          offers never land in GENERATED, they start directly as
                          OFFERED. Not conditionally hidden. */}
                      <th className="py-3 pr-4">Eligibility</th>
                      <th className="py-3 pr-5">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupsQuery.data.groups.map((group) => (
                      <tr key={group.restructureGroupId} className="border-b border-outline-variant dark:border-outline-variant/20">
                        <td className="py-4 pl-5 pr-4 text-body-md text-on-surface dark:text-on-background">{group.restructureGroupId}</td>
                        <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{group.custId}</td>
                        <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{group.offerType}</td>
                        <td className="py-4 pr-4">
                          <Chip tone={TIER_TONE[group.eligibilityTier]}>{group.eligibilityTier}</Chip>
                        </td>
                        <td className="py-4 pr-5">
                          <Link
                            to={`/restructuring-approval/${group.restructureGroupId}`}
                            className="text-label-lg font-semibold text-primary-container dark:text-primary-fixed-dim hover:underline"
                          >
                            Detail
                          </Link>
                        </td>
                      </tr>
                    ))}
                    {groupsQuery.data.groups.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-body-md text-on-surface-variant dark:text-surface-variant">
                          {tab === 'GENERATED' ? 'Tidak ada grup yang menunggu approval.' : 'Belum ada riwayat.'}
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>

            {groupsQuery.data.groups.length > 0 ? (
              <div className="flex items-center justify-between">
                <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
                  Showing {groupsQuery.data.pageInfo.showingFrom}-{groupsQuery.data.pageInfo.showingTo} of{' '}
                  {groupsQuery.data.pageInfo.totalGroups} groups
                </p>
                <Pagination
                  page={pagination.page}
                  totalPages={groupsQuery.data.pageInfo.totalPages}
                  onNext={pagination.nextPage}
                  onPrevious={pagination.previousPage}
                  onGoToPage={pagination.goToPage}
                />
              </div>
            ) : null}
          </>
        )}
      </div>
    </AppLayout>
  );
}
