import { useParams } from 'react-router-dom';
import AppLayout from '../layouts/AppLayout';
import Avatar from '../components/Avatar';
import CustomerSummaryCards from '../components/CustomerSummaryCards';
import AiBehavioralInsights from '../components/AiBehavioralInsights';
import AiReasoningCard from '../components/AiReasoningCard';
import RestructuringOptionsCard from '../components/RestructuringOptionsCard';
import CustomerContractsList from '../components/CustomerContractsList';
import CustomerDetailSkeleton from '../components/skeletons/CustomerDetailSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useCustomerDetailQuery } from '../domains/customer/useCustomerDetailQuery';
import { useCustomerContractsQuery } from '../domains/customer/useCustomerContractsQuery';
import { useRestructuringOptionsQuery } from '../domains/restructuring/useRestructuringOptionsQuery';

interface CustomerDetailPageProps {
  readonly className?: string;
}

export default function CustomerDetailPage({ className = '' }: CustomerDetailPageProps) {
  const { id = '' } = useParams<{ id: string }>();
  const detailQuery = useCustomerDetailQuery(id);
  const contractsQuery = useCustomerContractsQuery(id);
  const restructuringQuery = useRestructuringOptionsQuery(id);

  if (detailQuery.isLoading || contractsQuery.isLoading || restructuringQuery.isLoading) {
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

  if (restructuringQuery.isError || !restructuringQuery.data) {
    return (
      <AppLayout title="Customer Detail" searchPlaceholder="Search account..." badge="LIVE SYSTEM RECOVERY">
        <ErrorState message={toDisplayMessage(restructuringQuery.error)} onRetry={() => restructuringQuery.refetch()} />
      </AppLayout>
    );
  }

  if (contractsQuery.isError || !contractsQuery.data) {
    return (
      <AppLayout title="Customer Detail" searchPlaceholder="Search account..." badge="LIVE SYSTEM RECOVERY">
        <ErrorState message={toDisplayMessage(contractsQuery.error)} onRetry={() => contractsQuery.refetch()} />
      </AppLayout>
    );
  }

  const customer = detailQuery.data;

  return (
    <AppLayout title="Customer Detail" searchPlaceholder="Search account..." badge="LIVE SYSTEM RECOVERY">
      <div className={`space-y-6 ${className}`}>
        <div className="flex items-center justify-between bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
          <div className="flex items-center gap-4">
            <Avatar initials={customer.initials} size="lg" />
            <div>
              <p className="text-title-md font-bold text-on-surface dark:text-on-background">{customer.name}</p>
              <span className="text-label-md text-on-surface-variant dark:text-surface-variant">ID: {customer.custId}</span>
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

        <AiReasoningCard custId={customer.custId} />

        <RestructuringOptionsCard custId={customer.custId} assessment={restructuringQuery.data} />

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">
            <span className="material-symbols-outlined text-lg">description</span>
            Kontrak Milik Customer Ini
          </p>
          <CustomerContractsList contracts={contractsQuery.data} />
        </div>
      </div>
    </AppLayout>
  );
}
