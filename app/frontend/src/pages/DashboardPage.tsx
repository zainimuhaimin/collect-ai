import AppLayout from '../layouts/AppLayout';
import StatCard from '../components/StatCard';
import DpdBucketChart from '../components/DpdBucketChart';
import ChannelEfficiencyChart from '../components/ChannelEfficiencyChart';
import DashboardSkeleton from '../components/skeletons/DashboardSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useDashboardSummaryQuery } from '../domains/dashboard/useDashboardSummaryQuery';
import { RISK_SEGMENT_TONE, riskSegmentSchema } from '../domains/shared/riskSegment';
import { formatRupiah, formatPercentFromDecimal } from '../lib/format';
import Chip from '../components/Chip';

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

  // Fixed set of 4 real KPIs (see dashboard.schema.ts) — `icon` is a purely client-side
  // visual choice, not backend data (the old mock's `icon`/`change`/`trend` fields have
  // no backend source and were dropped).
  const kpiCards = [
    { icon: 'account_balance_wallet', label: 'Total Outstanding', value: formatRupiah(data.kpis.totalOutstanding) },
    {
      icon: 'person_off',
      label: 'Active Delinquent Accounts',
      value: data.kpis.activeDelinquentAccounts.toLocaleString('id-ID'),
    },
    {
      icon: 'verified',
      label: 'PTP Keep Rate',
      value: formatPercentFromDecimal(data.kpis.ptpKeepRate, 0),
    },
    { icon: 'fact_check', label: 'Manual Review Pending', value: data.kpis.manualReviewPending.toLocaleString('id-ID') },
  ];

  const riskSegmentEntries = Object.entries(data.riskSegmentDistribution);
  const totalRiskSegmentCount = riskSegmentEntries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <AppLayout title="Consolidated Dashboard" searchPlaceholder="Search debtor or ID...">
      <div className={`space-y-6 ${className}`}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {kpiCards.map((kpi) => (
            <StatCard key={kpi.label} icon={kpi.icon} label={kpi.label} value={kpi.value} />
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
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">Risk Segment Distribution</p>
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant mb-8">
              Proporsi risk segment portfolio
            </p>
            <div className="space-y-4">
              {riskSegmentEntries.map(([segment, count]) => {
                const percent = totalRiskSegmentCount > 0 ? (count / totalRiskSegmentCount) * 100 : 0;
                const parsedSegment = riskSegmentSchema.safeParse(segment);
                const tone = parsedSegment.success ? RISK_SEGMENT_TONE[parsedSegment.data] : 'neutral';
                return (
                  <div
                    key={segment}
                    className="flex items-center gap-3"
                    title={`${count.toLocaleString('id-ID')} kontrak`}
                  >
                    <span className="w-28 shrink-0">
                      <Chip tone={tone}>{segment}</Chip>
                    </span>
                    <div className="flex-1 h-6 rounded-md bg-surface-container-high dark:bg-surface-variant/10 overflow-hidden">
                      <div className="h-full rounded-md bg-primary-container" style={{ width: `${percent}%` }} />
                    </div>
                    <span className="w-14 shrink-0 text-right text-label-lg font-semibold text-on-surface dark:text-on-background">
                      {percent.toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">Channel Efficiency</p>
          <p className="text-body-md text-on-surface-variant dark:text-surface-variant mb-4">
            Contact success rate per treatment channel, diurutkan dari yang terbaik
          </p>
          <ChannelEfficiencyChart channels={data.channelEfficiency} />
        </div>

        <div className="flex items-center justify-between text-body-md text-on-surface-variant dark:text-surface-variant">
          <span>{data.syncNote}</span>
          <div className="flex items-center gap-6">
            <button
              type="button"
              disabled
              title="Belum didukung backend pada fase ini"
              className="flex items-center gap-1.5 opacity-40 cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-lg">download</span>
              Export Report
            </button>
            <button
              type="button"
              disabled
              title="Belum didukung backend pada fase ini"
              className="flex items-center gap-1.5 opacity-40 cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-lg">share</span>
              Share Insight
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
