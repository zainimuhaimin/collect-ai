import { useParams, Link } from 'react-router-dom';
import AppLayout from '../layouts/AppLayout';
import Chip from '../components/Chip';
import RestructuringGroupDetailSkeleton from '../components/skeletons/RestructuringGroupDetailSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useRestructuringGroupDetailQuery } from '../domains/restructuring/useRestructuringGroupDetailQuery';
import { useApproveRestructuringGroupMutation } from '../domains/restructuring/useApproveRestructuringGroupMutation';
import { useRejectRestructuringGroupMutation } from '../domains/restructuring/useRejectRestructuringGroupMutation';
import { formatRupiah } from '../lib/format';
import type { EligibilityTier } from '../domains/restructuring/restructuring.schema';

const TIER_TONE: Record<EligibilityTier, 'success' | 'medium' | 'danger'> = {
  AUTO: 'success',
  MANUAL_REVIEW: 'medium',
  BLOCKED: 'danger',
};

interface RestructuringGroupDetailPageProps {
  readonly className?: string;
}

function InfoRow({ label, value }: { readonly label: string; readonly value: string | number }) {
  return (
    <div>
      <p className="text-label-md text-on-surface-variant dark:text-surface-variant">{label}</p>
      <p className="text-body-md font-semibold text-on-surface dark:text-on-background">{value}</p>
    </div>
  );
}

export default function RestructuringGroupDetailPage({ className = '' }: RestructuringGroupDetailPageProps) {
  const { id = '' } = useParams<{ id: string }>();
  const detailQuery = useRestructuringGroupDetailQuery(id);
  const approveMutation = useApproveRestructuringGroupMutation();
  const rejectMutation = useRejectRestructuringGroupMutation();

  if (detailQuery.isLoading) {
    return (
      <AppLayout title="Restructuring Group Detail" searchPlaceholder="Search group or customer ID...">
        <RestructuringGroupDetailSkeleton />
      </AppLayout>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <AppLayout title="Restructuring Group Detail" searchPlaceholder="Search group or customer ID...">
        <ErrorState message={toDisplayMessage(detailQuery.error)} onRetry={() => detailQuery.refetch()} />
      </AppLayout>
    );
  }

  const group = detailQuery.data;
  const reasons = group.eligibilityReasons
    ? group.eligibilityReasons.split('; ').filter((reason) => reason.trim().length > 0)
    : [];
  // npv_baseline/npv_restructured_risk_adjusted are nullable per the real backend
  // contract — haven't observed a null case in practice, but guard against it anyway.
  const hasNpv = group.npvBaseline !== null && group.npvRestructuredRiskAdjusted !== null;
  const npvGain = (group.npvRestructuredRiskAdjusted ?? 0) - (group.npvBaseline ?? 0);
  const hasRawTotals = group.totalRemainingCurrent !== null && group.totalNewSchedule !== null;
  const canAct = group.offerStatus === 'GENERATED';

  return (
    <AppLayout title="Restructuring Group Detail" searchPlaceholder="Search group or customer ID...">
      <div className={`space-y-6 ${className}`}>
        <div className="flex items-center justify-between bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
          <div>
            <div className="flex items-center gap-2">
              <p className="text-title-md font-bold text-on-surface dark:text-on-background">{group.restructureGroupId}</p>
              <Chip tone="neutral">{group.offerType}</Chip>
              <Chip tone={group.offerStatus === 'REJECTED' ? 'danger' : 'success'}>{group.offerStatus}</Chip>
            </div>
            <Link
              to={`/customers/${group.custId}`}
              className="text-body-md text-primary-container dark:text-primary-fixed-dim hover:underline"
            >
              {group.custId}
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Ringkasan Grup</p>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="Contract Numbers" value={group.contractNos.join(', ')} />
              <InfoRow label="Offer Type" value={group.offerType} />
              <InfoRow label="Generated Date" value={group.generatedDate} />
              <InfoRow label="Status" value={group.offerStatus} />
            </div>
          </div>

          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">Eligibility</p>
              <Chip tone={TIER_TONE[group.eligibilityTier]}>{group.eligibilityTier}</Chip>
            </div>
            {reasons.length > 0 ? (
              <ul className="list-disc list-inside space-y-1 text-body-md text-on-surface-variant dark:text-surface-variant">
                {reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Tidak ada catatan eligibility.</p>
            )}
          </div>
        </div>

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Estimasi Hasil: Kontrak Saat Ini vs Setelah Restrukturisasi</p>
          {hasNpv ? (
            <>
              <div className="flex items-center justify-between rounded-lg bg-surface-container-low dark:bg-surface-container-high/10 px-4 py-3">
                <div>
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Estimasi Hasil — Kontrak Saat Ini</p>
                  <p className="text-title-md font-bold text-on-surface dark:text-on-background">{formatRupiah(group.npvBaseline!)}</p>
                </div>
                <span className="material-symbols-outlined text-on-surface-variant text-2xl">arrow_forward</span>
                <div className="text-right">
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Estimasi Hasil — Setelah Restrukturisasi</p>
                  <p className="text-title-md font-bold text-success">{formatRupiah(group.npvRestructuredRiskAdjusted!)}</p>
                </div>
              </div>
              <p className={`mt-3 text-label-lg font-semibold ${npvGain >= 0 ? 'text-success' : 'text-error'}`}>
                <span className="material-symbols-outlined align-middle text-lg mr-1">
                  {npvGain >= 0 ? 'trending_up' : 'trending_down'}
                </span>
                {npvGain >= 0 ? '+' : ''}
                {formatRupiah(npvGain)} dibanding kontrak saat ini
              </p>
            </>
          ) : (
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Data estimasi hasil tidak tersedia untuk grup ini.</p>
          )}

          {hasRawTotals ? (
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-outline-variant dark:border-outline-variant/30">
              <div>
                <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">Total Tagihan (Tanpa Diskon Risiko)</p>
                <p className="text-label-lg text-on-surface dark:text-on-background">{formatRupiah(group.totalRemainingCurrent!)}</p>
              </div>
              <span className="material-symbols-outlined text-base text-on-surface-variant">arrow_forward</span>
              <div className="text-right">
                <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">&nbsp;</p>
                <p className="text-label-lg text-on-surface dark:text-on-background">{formatRupiah(group.totalNewSchedule!)}</p>
              </div>
            </div>
          ) : null}
        </div>

        {canAct ? (
          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Supervisor Action</p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => approveMutation.mutate(group.restructureGroupId)}
                disabled={approveMutation.isPending || rejectMutation.isPending}
                className="px-4 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold disabled:opacity-40"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => rejectMutation.mutate(group.restructureGroupId)}
                disabled={approveMutation.isPending || rejectMutation.isPending}
                className="px-4 py-2.5 rounded-lg border border-outline-variant dark:border-outline-variant/30 text-label-lg disabled:opacity-40"
              >
                Reject
              </button>
            </div>
            {approveMutation.isError || rejectMutation.isError ? (
              <p className="mt-3 text-body-md text-error">
                {toDisplayMessage(approveMutation.error ?? rejectMutation.error)}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </AppLayout>
  );
}
