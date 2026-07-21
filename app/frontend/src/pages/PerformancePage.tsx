import { useState } from 'react';
import AppLayout from '../layouts/AppLayout';
import FilterSelectRow from '../components/FilterSelectRow';
import CollectorRankingTable from '../components/CollectorRankingTable';
import Pagination from '../components/Pagination';
import OperationalLogList from '../components/OperationalLogList';
import PerformanceSkeleton from '../components/skeletons/PerformanceSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { usePerformanceFiltersQuery } from '../domains/performance/usePerformanceFiltersQuery';
import { usePerformanceSummaryQuery } from '../domains/performance/usePerformanceSummaryQuery';
import { useCollectorRankingQuery } from '../domains/performance/useCollectorRankingQuery';
import { usePerformanceOperationalLogQuery } from '../domains/performance/usePerformanceOperationalLogQuery';

interface PerformancePageProps {
  readonly className?: string;
}

export default function PerformancePage({ className = '' }: PerformancePageProps) {
  const filtersQuery = usePerformanceFiltersQuery();
  const summaryQuery = usePerformanceSummaryQuery();
  const operationalLogQuery = usePerformanceOperationalLogQuery();

  // `page` lives here (not in the generic usePagination hook) because totalPages is only
  // known once rankingQuery resolves — usePagination's clamping needs that value up front,
  // which doesn't exist yet on the very first render.
  const [page, setPage] = useState(1);
  const rankingQuery = useCollectorRankingQuery(page);
  const totalPages = rankingQuery.data?.pageInfo.totalPages ?? 1;
  const goToPage = (target: number) => setPage(Math.min(Math.max(target, 1), totalPages));
  const nextPage = () => goToPage(page + 1);
  const previousPage = () => goToPage(page - 1);

  const isLoading = filtersQuery.isLoading || summaryQuery.isLoading || rankingQuery.isLoading || operationalLogQuery.isLoading;
  if (isLoading) {
    return (
      <AppLayout title="Performance" searchPlaceholder="Search data...">
        <PerformanceSkeleton />
      </AppLayout>
    );
  }

  const firstError = [filtersQuery, summaryQuery, rankingQuery, operationalLogQuery].find((query) => query.isError);
  if (firstError || !filtersQuery.data || !summaryQuery.data || !rankingQuery.data || !operationalLogQuery.data) {
    return (
      <AppLayout title="Performance" searchPlaceholder="Search data...">
        <ErrorState message={toDisplayMessage(firstError?.error)} onRetry={() => firstError?.refetch()} />
      </AppLayout>
    );
  }

  const filters = filtersQuery.data;
  const summary = summaryQuery.data;
  const ranking = rankingQuery.data;

  return (
    <AppLayout title="Performance" searchPlaceholder="Search data...">
      <div className={`space-y-6 ${className}`}>
        <FilterSelectRow
          filters={[
            { label: 'Branch', options: filters.branches },
            { label: 'Area', options: filters.areas },
            { label: 'Product', options: filters.products },
          ]}
          dateRangeLabel={filters.dateRange}
        />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl bg-primary-container text-on-primary p-5">
            <div className="flex items-center justify-between">
              <p className="text-body-md text-on-primary-container">Total Achievement</p>
              <span className="material-symbols-outlined">payments</span>
            </div>
            <p className="text-title-lg font-bold mt-2">{summary.totalAchievement}</p>
            <p className="text-label-md text-on-primary-container mt-1">
              <span className="material-symbols-outlined text-sm align-middle">trending_up</span> {summary.achievementChange}
            </p>
          </div>
          <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 p-5">
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Active Collectors</p>
            <p className="text-title-lg font-bold text-on-surface dark:text-on-background mt-2">{summary.activeCollectors} Users</p>
            <div className="h-1.5 rounded-full bg-surface-container-high dark:bg-surface-variant/20 mt-3 overflow-hidden">
              <div className="h-full bg-on-background dark:bg-on-surface" style={{ width: `${summary.activeCollectorsProgress}%` }} />
            </div>
          </div>
          <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 p-5">
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Avg Productivity Index</p>
            <p className="text-title-lg font-bold text-on-surface dark:text-on-background mt-2">{summary.avgProductivityIndex}</p>
          </div>
        </div>

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">Collector Ranking &amp; Productivity</p>
            <div className="flex items-center gap-2">
              <button type="button" className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-outline-variant dark:border-outline-variant/30 text-label-lg">
                <span className="material-symbols-outlined text-lg">download</span>
                Export CSV
              </button>
              <button type="button" className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold">
                <span className="material-symbols-outlined text-lg">add</span>
                Bulk Action
              </button>
            </div>
          </div>
          <CollectorRankingTable collectors={ranking.collectors} />
          <div className="flex items-center justify-between mt-4">
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
              Showing {ranking.pageInfo.showingFrom} to {ranking.pageInfo.showingTo} of {ranking.pageInfo.totalCollectors} collectors
            </p>
            <Pagination page={page} totalPages={totalPages} onNext={nextPage} onPrevious={previousPage} onGoToPage={goToPage} />
          </div>
        </div>

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">
            <span className="material-symbols-outlined text-lg">history</span>
            Log Operasional Terkini
          </p>
          <OperationalLogList entries={operationalLogQuery.data} />
        </div>
      </div>
    </AppLayout>
  );
}
