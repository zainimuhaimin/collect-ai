import { useParams } from 'react-router-dom';
import AppLayout from '../layouts/AppLayout';
import Avatar from '../components/Avatar';
import Chip from '../components/Chip';
import CustomerSummaryCards from '../components/CustomerSummaryCards';
import AiBehavioralInsights from '../components/AiBehavioralInsights';
import AiJustificationBanner from '../components/AiJustificationBanner';
import ActivityTimeline from '../components/ActivityTimeline';
import CustomerDetailSkeleton from '../components/skeletons/CustomerDetailSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useCustomerDetailQuery } from '../domains/customer/useCustomerDetailQuery';
import { useCustomerTimelineQuery } from '../domains/customer/useCustomerTimelineQuery';

interface CustomerDetailPageProps {
  readonly className?: string;
}

export default function CustomerDetailPage({ className = '' }: CustomerDetailPageProps) {
  const { id = '' } = useParams<{ id: string }>();
  const detailQuery = useCustomerDetailQuery(id);
  const timelineQuery = useCustomerTimelineQuery(id);

  if (detailQuery.isLoading || timelineQuery.isLoading) {
    return (
      <AppLayout title="Customer Detail" searchPlaceholder="Search account..." badge="LIVE SYSTEM RECOVERY">
        <CustomerDetailSkeleton />
      </AppLayout>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <AppLayout title="Customer Detail" searchPlaceholder="Search account..." badge="LIVE SYSTEM RECOVERY">
        <ErrorState message={toDisplayMessage(detailQuery.error)} onRetry={() => detailQuery.refetch()} />
      </AppLayout>
    );
  }

  if (timelineQuery.isError || !timelineQuery.data) {
    return (
      <AppLayout title="Customer Detail" searchPlaceholder="Search account..." badge="LIVE SYSTEM RECOVERY">
        <ErrorState message={toDisplayMessage(timelineQuery.error)} onRetry={() => timelineQuery.refetch()} />
      </AppLayout>
    );
  }

  const customer = detailQuery.data;
  const timeline = timelineQuery.data;

  return (
    <AppLayout title="Customer Detail" searchPlaceholder="Search account..." badge="LIVE SYSTEM RECOVERY">
      <div className={`space-y-6 ${className}`}>
        <div className="flex items-center justify-between bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
          <div className="flex items-center gap-4">
            <Avatar initials={customer.initials} size="lg" />
            <div>
              <p className="text-title-md font-bold text-on-surface dark:text-on-background">{customer.name}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-label-md text-on-surface-variant dark:text-surface-variant">ID: #{customer.id}</span>
                {customer.verified ? (
                  <Chip tone="success">
                    <span className="material-symbols-outlined text-xs">verified</span>
                    Verified Account
                  </Chip>
                ) : null}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="px-4 py-2.5 rounded-lg border border-outline-variant dark:border-outline-variant/30 text-label-lg">
              Assign Agent
            </button>
            <button type="button" className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold">
              <span className="material-symbols-outlined text-lg">call</span>
              Create Action
            </button>
          </div>
        </div>

        <CustomerSummaryCards customer={customer} />

        <AiBehavioralInsights customer={customer} />

        <AiJustificationBanner justification={customer.aiJustification} />

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background mb-6">
            <span className="material-symbols-outlined text-lg">history</span>
            Collection Activity Timeline
          </p>
          <ActivityTimeline items={timeline} />
          <div className="flex justify-center mt-6">
            <button type="button" className="px-5 py-2.5 rounded-lg border border-outline-variant dark:border-outline-variant/30 text-label-lg">
              Load Full History
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
