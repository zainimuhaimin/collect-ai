import AppLayout from '../layouts/AppLayout';
import FilterChips from '../components/FilterChips';
import AccountListItem from '../components/AccountListItem';
import AiReasoningCard from '../components/AiReasoningCard';
import ActivityTimeline, { type TimelineItem } from '../components/ActivityTimeline';
import ProgressBar from '../components/ProgressBar';
import WorkbenchSkeleton from '../components/skeletons/WorkbenchSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useWorkbenchFilter } from '../hooks/useWorkbenchFilter';
import { useWorkbenchActivityLogQuery } from '../domains/workbench/useWorkbenchActivityLogQuery';
import type { WorkbenchFilterKey } from '../domains/workbench/workbench.schema';

interface CollectorWorkbenchPageProps {
  readonly className?: string;
}

const workbenchSortLabel = 'Urutkan: Critical First';

function filterLabel(key: WorkbenchFilterKey, totalCount: number): string {
  if (key === 'all') return `Semua Akun (${totalCount})`;
  if (key === 'dpd_30_plus') return 'DPD 30+';
  return 'High Amount';
}

const FILTER_KEYS: WorkbenchFilterKey[] = ['all', 'dpd_30_plus', 'high_amount'];

export default function CollectorWorkbenchPage({ className = '' }: CollectorWorkbenchPageProps) {
  const {
    activeFilter,
    setActiveFilter,
    searchQuery,
    setSearchQuery,
    accounts,
    totalCount,
    selectedAccount,
    selectedAccountId,
    setSelectedAccountId,
    isLoading,
    isError,
    error,
    refetch,
  } = useWorkbenchFilter();
  const activityLogQuery = useWorkbenchActivityLogQuery();

  if (isLoading || activityLogQuery.isLoading) {
    return (
      <AppLayout title="Collector Workbench" searchPlaceholder="Cari Debitur...">
        <WorkbenchSkeleton />
      </AppLayout>
    );
  }

  if (isError || activityLogQuery.isError || !activityLogQuery.data || !selectedAccount) {
    return (
      <AppLayout title="Collector Workbench" searchPlaceholder="Cari Debitur...">
        <ErrorState message={toDisplayMessage(error ?? activityLogQuery.error)} onRetry={() => (isError ? refetch() : activityLogQuery.refetch())} />
      </AppLayout>
    );
  }

  const activityTimelineItems: TimelineItem[] = activityLogQuery.data.map((entry) => ({
    id: entry.id,
    title: entry.title,
    timestamp: entry.timestamp,
    tone: entry.tone === 'sent' ? 'default' : 'muted',
  }));

  const filterOptions = FILTER_KEYS.map((key) => filterLabel(key, totalCount));
  const handleFilterSelect = (label: string) => {
    const matched = FILTER_KEYS.find((key) => filterLabel(key, totalCount) === label);
    if (matched) setActiveFilter(matched);
  };

  return (
    <AppLayout title="Collector Workbench" searchPlaceholder="Cari Debitur...">
      <div className={`grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-6 ${className}`}>
        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between gap-4 p-4 border-b border-outline-variant dark:border-outline-variant/30">
            <FilterChips options={filterOptions} activeOption={filterLabel(activeFilter, totalCount)} onSelect={handleFilterSelect} />
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Cari nama debitur..."
              className="w-40 shrink-0 px-3 py-1.5 rounded-lg bg-surface-container-low dark:bg-surface-container-high/20 text-label-md text-on-surface dark:text-on-background placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary-container"
            />
            <span className="flex items-center gap-1.5 text-label-md text-on-surface-variant dark:text-surface-variant whitespace-nowrap">
              <span className="material-symbols-outlined text-lg">sort</span>
              {workbenchSortLabel}
            </span>
          </div>
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-2 text-label-md uppercase text-on-surface-variant dark:text-surface-variant border-b border-outline-variant dark:border-outline-variant/20">
            <span>Customer Name</span>
            <span>DPD</span>
            <span>Amount (Rp)</span>
            <span>Priority</span>
          </div>
          {accounts.map((account) => (
            <AccountListItem
              key={account.id}
              account={account}
              isSelected={account.id === selectedAccountId}
              onSelect={() => setSelectedAccountId(account.id)}
            />
          ))}
        </div>

        <div className="space-y-4">
          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
            <p className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant">Profil Debitur</p>
            <div className="flex items-start justify-between mt-1">
              <div>
                <p className="text-title-md font-bold text-on-surface dark:text-on-background">{selectedAccount.name}</p>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant">{selectedAccount.location}</p>
              </div>
              <div className="text-center bg-primary-container text-on-primary rounded-lg px-3 py-1.5">
                <p className="text-label-sm">Score</p>
                <p className="text-label-lg font-bold">{selectedAccount.paymentProbability}%</p>
              </div>
            </div>
            <div className="flex items-center justify-between mt-4 mb-1.5">
              <span className="text-label-md text-on-surface-variant dark:text-surface-variant">Probabilitas Pembayaran</span>
              <span className="text-label-md font-semibold text-on-surface dark:text-on-background">
                {selectedAccount.paymentProbability}% (Tinggi)
              </span>
            </div>
            <ProgressBar value={selectedAccount.paymentProbability} tone="primary" />
          </div>

          <div>
            <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background mb-3">
              <span className="material-symbols-outlined text-lg">psychology</span>
              AI Reasoning &amp; Analisis
            </p>
            <AiReasoningCard reasoning={selectedAccount.aiReasoning} recommendations={selectedAccount.aiRecommendations} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="border border-outline-variant dark:border-outline-variant/30 rounded-xl p-4">
              <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Status Pekerjaan</p>
              <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mt-1">
                {selectedAccount.employmentStatus}
              </p>
            </div>
            <div className="border border-outline-variant dark:border-outline-variant/30 rounded-xl p-4">
              <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Terakhir Bayar</p>
              <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mt-1">
                {selectedAccount.lastPaymentDate}
              </p>
            </div>
          </div>

          <div className="border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Log Operasional Terakhir</p>
            <ActivityTimeline items={activityTimelineItems} />
          </div>

          <div className="flex items-center gap-3 sticky bottom-0 bg-surface dark:bg-surface-container-lowest pt-2">
            <button type="button" className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg bg-secondary-container text-on-secondary-container font-semibold text-label-lg">
              <span className="material-symbols-outlined text-lg">chat</span>
              Kirim WA
            </button>
            <button type="button" className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg bg-primary-container text-on-primary font-semibold text-label-lg">
              <span className="material-symbols-outlined text-lg">call</span>
              Hubungi Deskcoll
            </button>
            <button type="button" aria-label="More actions" className="p-3 rounded-lg border border-outline-variant dark:border-outline-variant/30">
              <span className="material-symbols-outlined text-lg">more_vert</span>
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
