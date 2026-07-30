import type { RestructuringAssessment, EligibilityTier } from '../domains/restructuring/restructuring.schema';
import { useSubmitCustomerResponseMutation } from '../domains/restructuring/useSubmitCustomerResponseMutation';
import { formatRupiah, formatPercentFromDecimal } from '../lib/format';
import Chip from './Chip';

interface RestructuringOptionsCardProps {
  readonly custId: string;
  readonly assessment: RestructuringAssessment;
}

const TIER_TONE: Record<EligibilityTier, 'success' | 'medium' | 'danger'> = {
  AUTO: 'success',
  MANUAL_REVIEW: 'medium',
  BLOCKED: 'danger',
};

export default function RestructuringOptionsCard({ custId, assessment }: RestructuringOptionsCardProps) {
  const submitResponse = useSubmitCustomerResponseMutation();

  const hasResponded = assessment.customerResponse !== null;
  const waitingForSupervisor = !hasResponded && assessment.eligibilityTier !== 'AUTO' && !assessment.canRespond;
  const canAct = !hasResponded && !waitingForSupervisor && assessment.canRespond;

  const handleRespond = (response: 'ACCEPTED' | 'REJECTED') => {
    // `canAct` (gating the buttons below) is only ever true when canRespond is
    // true, which the backend only sets when restructureGroupId is non-null —
    // this guard just satisfies the type checker for that runtime invariant.
    if (!assessment.restructureGroupId) return;
    submitResponse.mutate({ custId, groupId: assessment.restructureGroupId, response });
  };

  return (
    <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10">
        <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background">
          <span className="material-symbols-outlined text-lg">handshake</span>
          Opsi Restrukturisasi
        </p>
        <Chip tone={TIER_TONE[assessment.eligibilityTier]}>{assessment.eligibilityTier}</Chip>
      </div>

      <div className="p-5 space-y-4">
        {assessment.eligibilityReasons.length > 0 ? (
          <ul className="list-disc list-inside space-y-1 text-body-md text-on-surface-variant dark:text-surface-variant">
            {assessment.eligibilityReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}

        {assessment.offers.length === 0 ? (
          <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
            Tidak ada opsi restrukturisasi yang tersedia untuk customer ini saat ini.
          </p>
        ) : (
          assessment.offers.map((offer) => (
            <div
              key={`${offer.offerType}-${offer.contractNos.join('-')}`}
              className="rounded-lg border border-outline-variant dark:border-outline-variant/30 p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-label-lg font-semibold text-on-surface dark:text-on-background">{offer.offerType}</span>
                <span className="text-label-sm text-on-surface-variant dark:text-surface-variant">
                  Kontrak: {offer.contractNos.join(', ')}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-body-md">
                <div>
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Tenor Baru</p>
                  <p className="font-semibold text-on-surface dark:text-on-background">{offer.recommendedNewTenorMonths} bulan</p>
                </div>
                <div>
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Rate Baru</p>
                  <p className="font-semibold text-on-surface dark:text-on-background">{formatPercentFromDecimal(offer.recommendedNewRate)}</p>
                </div>
                <div>
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Cicilan Baru</p>
                  <p className="font-semibold text-on-surface dark:text-on-background">{formatRupiah(offer.recommendedNewInstallment)}</p>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-surface-container-low dark:bg-surface-container-high/10 px-4 py-3">
                <div>
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Estimasi Hasil — Kontrak Saat Ini</p>
                  <p className="font-semibold text-on-surface dark:text-on-background">{formatRupiah(offer.npvBaseline)}</p>
                </div>
                <span className="material-symbols-outlined text-on-surface-variant">arrow_forward</span>
                <div className="text-right">
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant">Estimasi Hasil — Setelah Restrukturisasi</p>
                  <p className="font-semibold text-success">{formatRupiah(offer.npvRestructuredRiskAdjusted)}</p>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg px-4 py-2">
                <div>
                  <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">
                    Total Tagihan (Tanpa Diskon Risiko)
                  </p>
                  <p className="text-label-lg text-on-surface dark:text-on-background">{formatRupiah(offer.totalRemainingCurrent)}</p>
                </div>
                <span className="material-symbols-outlined text-base text-on-surface-variant">arrow_forward</span>
                <div className="text-right">
                  <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">&nbsp;</p>
                  <p className="text-label-lg text-on-surface dark:text-on-background">{formatRupiah(offer.totalNewSchedule)}</p>
                </div>
              </div>
            </div>
          ))
        )}

        {assessment.offers.length > 0 ? (
          <div>
            {hasResponded ? (
              <div className="flex items-center gap-2 rounded-lg bg-success-container dark:bg-success/10 px-4 py-3 text-label-lg font-semibold text-on-success-container dark:text-success-container">
                <span className="material-symbols-outlined text-lg">check_circle</span>
                Customer sudah merespons: {assessment.customerResponse}
              </div>
            ) : waitingForSupervisor ? (
              <div className="flex items-center gap-2 rounded-lg bg-surface-container-high dark:bg-surface-variant/10 px-4 py-3 text-label-lg text-on-surface-variant dark:text-surface-variant">
                <span className="material-symbols-outlined text-lg">hourglass_empty</span>
                Menunggu approval supervisor
              </div>
            ) : null}

            <div className="flex items-center gap-2 mt-3">
              <button
                type="button"
                onClick={() => handleRespond('ACCEPTED')}
                disabled={!canAct || submitResponse.isPending}
                className="flex-1 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold disabled:opacity-40"
              >
                Terima
              </button>
              <button
                type="button"
                onClick={() => handleRespond('REJECTED')}
                disabled={!canAct || submitResponse.isPending}
                className="flex-1 py-2.5 rounded-lg border border-outline-variant dark:border-outline-variant/30 text-label-lg disabled:opacity-40"
              >
                Tolak
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
