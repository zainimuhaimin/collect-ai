import { useParams, Link } from 'react-router-dom';
import AppLayout from '../layouts/AppLayout';
import Chip from '../components/Chip';
import ProgressBar from '../components/ProgressBar';
import ActivityTimeline from '../components/ActivityTimeline';
import ContractDetailSkeleton from '../components/skeletons/ContractDetailSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useContractDetailQuery } from '../domains/contract/useContractDetailQuery';
import { useContractActivityLogQuery } from '../domains/contract/useContractActivityLogQuery';
import { RISK_SEGMENT_TONE } from '../domains/shared/riskSegment';
import { formatRupiah, formatPercentFromDecimal, formatDateHuman } from '../lib/format';

interface ContractDetailPageProps {
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

export default function ContractDetailPage({ className = '' }: ContractDetailPageProps) {
  const { contractNo = '' } = useParams<{ contractNo: string }>();
  const detailQuery = useContractDetailQuery(contractNo);
  const activityLogQuery = useContractActivityLogQuery(contractNo);

  // Only the main detail query gates the whole page — the activity-log/timeline query
  // has its own isolated loading/error rendering scoped to just that section below, so
  // a failure there (e.g. a still-malformed entry) doesn't blank the entire page.
  if (detailQuery.isLoading) {
    return (
      <AppLayout title="Contract Detail" searchPlaceholder="Search contract...">
        <ContractDetailSkeleton />
      </AppLayout>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <AppLayout title="Contract Detail" searchPlaceholder="Search contract...">
        <ErrorState message={toDisplayMessage(detailQuery.error)} onRetry={() => detailQuery.refetch()} />
      </AppLayout>
    );
  }

  const contract = detailQuery.data;

  return (
    <AppLayout title="Contract Detail" searchPlaceholder="Search contract...">
      <div className={`space-y-6 ${className}`}>
        {/* 1. Header */}
        <div className="flex items-center justify-between bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
          <div>
            <div className="flex items-center gap-2">
              <p className="text-title-md font-bold text-on-surface dark:text-on-background">{contract.contractNo}</p>
              <Chip tone="neutral">{contract.productType}</Chip>
              <Chip tone="medium">Cycle {contract.cycle}</Chip>
              {contract.closedViaRestructure ? <Chip tone="success">Direstrukturisasi →</Chip> : null}
            </div>
            <Link
              to={`/customers/${contract.custId}`}
              className="text-body-md text-primary-container dark:text-primary-fixed-dim hover:underline"
            >
              {contract.custName} ({contract.custId})
            </Link>
          </div>
        </div>

        {/* 2 & 3. Ringkasan Kontrak + Rincian Outstanding */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Ringkasan Kontrak</p>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="Jumlah Pinjaman" value={formatRupiah(contract.loanAmount)} />
              <InfoRow label="Cicilan" value={formatRupiah(contract.installmentAmount)} />
              <InfoRow label="Suku Bunga" value={formatPercentFromDecimal(contract.interestRate)} />
              <InfoRow label="Jatuh Tempo" value={formatDateHuman(contract.maturityDate)} />
              <InfoRow label="Sisa Tenor" value={`${contract.remainingTenorMonths} bulan`} />
              <InfoRow label="DPD Saat Ini" value={contract.dpdCurrent} />
              <InfoRow label="Cicilan Menunggak" value={contract.overdueInstallmentCount} />
              <InfoRow label="Denda Keterlambatan" value={formatRupiah(contract.lateFeeAmount)} />
              <InfoRow label="AMBC" value={formatRupiah(contract.ambc)} />
              <InfoRow label="Siklus Sebelumnya" value={contract.prevCycle ?? '—'} />
            </div>
          </div>

          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Rincian Outstanding</p>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Pokok (Principal)</span>
                <span className="text-body-md font-semibold text-on-surface dark:text-on-background">
                  {formatRupiah(contract.outstanding.principal)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Bunga (Interest)</span>
                <span className="text-body-md font-semibold text-on-surface dark:text-on-background">
                  {formatRupiah(contract.outstanding.interest)}
                </span>
              </div>
              <div className="flex items-center justify-between pt-3 border-t border-outline-variant dark:border-outline-variant/30">
                <span className="text-label-lg font-semibold text-on-surface dark:text-on-background">Total Outstanding</span>
                <span className="text-title-md font-bold text-on-surface dark:text-on-background">
                  {formatRupiah(contract.outstanding.total)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 4. AI Scoring */}
        <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">AI Scoring</p>
            <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">
              Scored: {formatDateHuman(contract.aiScoring?.scoringDate)}
            </p>
          </div>
          {contract.aiScoring ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5">
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Recovery Score</p>
                <span className="w-10 h-10 rounded-full border-2 border-primary-container dark:border-primary-fixed-dim inline-flex items-center justify-center text-label-lg font-bold">
                  {Math.round(contract.aiScoring.recoveryScore * 100)}
                </span>
              </div>
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Risk Segment</p>
                {contract.aiScoring.riskSegment ? (
                  <Chip tone={RISK_SEGMENT_TONE[contract.aiScoring.riskSegment]}>{contract.aiScoring.riskSegment}</Chip>
                ) : (
                  '—'
                )}
              </div>
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Self-Cure Prob %</p>
                <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">
                  {formatPercentFromDecimal(contract.aiScoring.selfCureProbability, 0)}
                </p>
                <ProgressBar
                  value={contract.aiScoring.selfCureProbability * 100}
                  tone="primary"
                  title={formatPercentFromDecimal(contract.aiScoring.selfCureProbability)}
                />
              </div>
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Roll-Forward Risk %</p>
                <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">
                  {formatPercentFromDecimal(contract.aiScoring.rollForwardRisk, 0)}
                </p>
                <ProgressBar
                  value={contract.aiScoring.rollForwardRisk * 100}
                  tone="error"
                  title={formatPercentFromDecimal(contract.aiScoring.rollForwardRisk)}
                />
              </div>
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">PTP Success Prob %</p>
                <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">
                  {formatPercentFromDecimal(contract.aiScoring.ptpSuccessProbability, 0)}
                </p>
                <ProgressBar
                  value={contract.aiScoring.ptpSuccessProbability * 100}
                  tone="primary"
                  title={formatPercentFromDecimal(contract.aiScoring.ptpSuccessProbability)}
                />
              </div>
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">NBA Recommendation</p>
                <p className="text-body-md font-semibold text-on-surface dark:text-on-background">
                  {contract.aiScoring.nbaRecommendation ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Confidence Level</p>
                <p className="text-body-md font-semibold text-on-surface dark:text-on-background">
                  {formatPercentFromDecimal(contract.aiScoring.confidenceLevel, 0)}
                </p>
              </div>
            </div>
          ) : (
            <p className="p-5 text-body-md text-on-surface-variant dark:text-surface-variant">
              Kontrak ini belum pernah di-scoring.
            </p>
          )}
        </div>

        {/* 5. Riwayat Pembayaran */}
        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Riwayat Pembayaran</p>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant border-b border-outline-variant dark:border-outline-variant/30">
                  <th className="py-3 pr-4">Jatuh Tempo</th>
                  <th className="py-3 pr-4">Tanggal Bayar</th>
                  <th className="py-3 pr-4">Jumlah</th>
                  <th className="py-3 pr-4">Status</th>
                  <th className="py-3 pr-4">Telat (Hari)</th>
                  <th className="py-3 pr-4">Sumber Recovery</th>
                </tr>
              </thead>
              <tbody>
                {contract.paymentHistory.map((payment, index) => (
                  <tr key={`${payment.dueDate ?? 'unknown'}-${index}`} className="border-b border-outline-variant dark:border-outline-variant/20">
                    <td className="py-3 pr-4 text-body-md text-on-surface dark:text-on-background">{formatDateHuman(payment.dueDate)}</td>
                    <td className="py-3 pr-4 text-body-md text-on-surface dark:text-on-background">{formatDateHuman(payment.actualPayDate)}</td>
                    <td className="py-3 pr-4 text-body-md text-on-surface dark:text-on-background">{formatRupiah(payment.paymentAmount)}</td>
                    <td className="py-3 pr-4">
                      <Chip tone={payment.payStatus === 'ON_TIME' ? 'success' : payment.payStatus === 'UNPAID' ? 'danger' : 'medium'}>
                        {payment.payStatus ?? '—'}
                      </Chip>
                    </td>
                    <td className="py-3 pr-4 text-body-md text-on-surface dark:text-on-background">{payment.delayDays ?? '—'}</td>
                    <td className="py-3 pr-4 text-body-md text-on-surface dark:text-on-background">{payment.recoverySource ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 6. Collection Activity Timeline */}
        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background mb-6">
            <span className="material-symbols-outlined text-lg">history</span>
            Collection Activity Timeline
          </p>
          {activityLogQuery.isLoading ? (
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Memuat log aktivitas...</p>
          ) : activityLogQuery.isError || !activityLogQuery.data ? (
            <ErrorState message={toDisplayMessage(activityLogQuery.error)} onRetry={() => activityLogQuery.refetch()} />
          ) : (
            <ActivityTimeline items={activityLogQuery.data} />
          )}
        </div>

        {/* 7. Status Restrukturisasi (read-only) */}
        <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 p-6">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-3">Status Restrukturisasi</p>
          {contract.restructuringStatus ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Group ID</span>
                <span className="text-body-md font-semibold text-on-surface dark:text-on-background">
                  {contract.restructuringStatus.restructureGroupId}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Offer Status</span>
                <Chip tone="medium">{contract.restructuringStatus.offerStatus}</Chip>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Eligibility Tier</span>
                <Chip tone="neutral">{contract.restructuringStatus.eligibilityTier}</Chip>
              </div>
            </div>
          ) : (
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Belum pernah direstrukturisasi.</p>
          )}
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mt-4">
            Lihat & respons di halaman{' '}
            <Link to={`/customers/${contract.custId}`} className="text-primary-container dark:text-primary-fixed-dim hover:underline">
              Customer
            </Link>
            .
          </p>
        </div>
      </div>
    </AppLayout>
  );
}
