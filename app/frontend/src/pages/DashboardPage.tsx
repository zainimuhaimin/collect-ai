import AppLayout from '../layouts/AppLayout';
import StatCard from '../components/StatCard';
import DpdBucketChart from '../components/DpdBucketChart';
import ContactabilityFunnel from '../components/ContactabilityFunnel';
import PriorityAccountsTable from '../components/PriorityAccountsTable';
import DashboardSkeleton from '../components/skeletons/DashboardSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useDashboardSummaryQuery } from '../domains/dashboard/useDashboardSummaryQuery';

interface DashboardPageProps {
  readonly className?: string;
}

export default function DashboardPage({ className = '' }: DashboardPageProps) {
  const { data, isLoading, isError, error, refetch } = useDashboardSummaryQuery();

  if (isLoading) {
    return (
      <AppLayout title="Consolidated Dashboard" searchPlaceholder="Search debtor or ID...">
        <DashboardSkeleton />
      </AppLayout>
    );
  }

  if (isError || !data) {
    return (
      <AppLayout title="Consolidated Dashboard" searchPlaceholder="Search debtor or ID...">
        <ErrorState message={toDisplayMessage(error)} onRetry={() => refetch()} />
      </AppLayout>
    );
  }

  return (
    <AppLayout title="Consolidated Dashboard" searchPlaceholder="Search debtor or ID...">
      <div className={`space-y-6 ${className}`}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {data.kpis.map((kpi) => (
            <StatCard key={kpi.label} stat={kpi} />
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">DPD Buckets vs PTP Status</p>
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant mb-4">
              Portfolio distribution by aging and commitment
            </p>
            <DpdBucketChart buckets={data.dpdBuckets} />
          </div>

          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">Contactability Funnel</p>
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant mb-4">
              Efficiency of omni-channel recovery
            </p>
            <ContactabilityFunnel
              stages={data.contactabilityFunnel}
              channel={data.channelEfficiency.channel}
              channelRate={data.channelEfficiency.rate}
            />
          </div>
        </div>

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">Broken PTP - High AMBC Priorities</p>
              <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
                Accounts requiring immediate manual intervention based on Artificial Intelligence Behavioral Analysis
              </p>
            </div>
            <button type="button" className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold">
              <span className="material-symbols-outlined text-lg">library_add_check</span>
              Bulk Assign
            </button>
          </div>
          <PriorityAccountsTable accounts={data.brokenPtpPriorities} />
        </div>

        <div className="flex items-center justify-between text-body-md text-on-surface-variant dark:text-surface-variant">
          <span>{data.syncNote}</span>
          <div className="flex items-center gap-6">
            <button type="button" className="flex items-center gap-1.5 hover:text-on-surface dark:hover:text-on-background">
              <span className="material-symbols-outlined text-lg">download</span>
              Export Report
            </button>
            <button type="button" className="flex items-center gap-1.5 hover:text-on-surface dark:hover:text-on-background">
              <span className="material-symbols-outlined text-lg">share</span>
              Share Insight
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
