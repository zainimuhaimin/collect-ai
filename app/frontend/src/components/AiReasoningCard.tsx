import Chip, { type ChipTone } from './Chip';
import { ApiError, toDisplayMessage } from '../api/apiError';
import { useAiReasoningQuery } from '../domains/ai-reasoning/useAiReasoningQuery';
import { useGenerateAiReasoningMutation } from '../domains/ai-reasoning/useGenerateAiReasoningMutation';
import type { PerContractFocus } from '../domains/ai-reasoning/aiReasoning.schema';

interface AiReasoningCardProps {
  readonly custId: string;
}

const URGENCY_TONE: Record<PerContractFocus['urgency'], ChipTone> = {
  LOW: 'neutral',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
};

// CRITICAL first, so the contract needing the most urgent action is always
// on top regardless of the order the API happens to return.
const URGENCY_ORDER: Record<PerContractFocus['urgency'], number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

const INSUFFICIENT_REASON_LABEL: Record<string, string> = {
  NO_CBS: 'belum memiliki profil perilaku (CBS)',
  TOO_FEW_PAYMENTS: 'belum memiliki riwayat pembayaran yang cukup',
  NO_SCORE: 'belum pernah discoring',
  TOO_MANY_CONTRACTS: 'memiliki jumlah kontrak aktif di luar batas normal — butuh penanganan manual',
};

export default function AiReasoningCard({ custId }: AiReasoningCardProps) {
  const query = useAiReasoningQuery(custId);
  const mutation = useGenerateAiReasoningMutation(custId);

  const handleGenerate = () => {
    mutation.mutate(undefined, {
      onError: (error) => {
        // 409 = generate lain untuk debitur ini sedang berjalan — bukan error
        // untuk ditampilkan, GET akan otomatis ter-refresh (onSettled hook di
        // mutation) begitu generate yang sedang berjalan itu selesai.
        if (error instanceof ApiError && (error.status === 409 || error.status === 429)) {
          return;
        }
      },
    });
  };

  if (query.isLoading) {
    return (
      <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 p-5">
        <div className="h-24 rounded-lg bg-surface-container-high/40 dark:bg-surface-container-high/10 animate-pulse" />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 p-5">
        <p className="flex items-center gap-1.5 text-body-md text-on-surface-variant dark:text-surface-variant">
          <span className="material-symbols-outlined text-lg">error</span>
          {toDisplayMessage(query.error)}
        </p>
      </div>
    );
  }

  const data = query.data;
  const isBusy = mutation.isPending;

  const showGenerateButton =
    data.status === 'NONE' ||
    data.status === 'DISABLED' ||
    data.status === 'INSUFFICIENT_DATA' ||
    data.status === 'FAILED';
  const showResult = data.status === 'OK' || data.status === 'FALLBACK';
  const sortedFocus = [...data.perContractFocus].sort(
    (a, b) => URGENCY_ORDER[a.urgency] - URGENCY_ORDER[b.urgency],
  );

  return (
    <div className="rounded-xl overflow-hidden border border-outline-variant dark:border-outline-variant/30">
      <div className="flex items-center justify-between px-5 py-4 bg-surface-container-lowest dark:bg-surface-container-high/10 border-b border-outline-variant dark:border-outline-variant/30">
        <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background">
          <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary-container/10 dark:bg-primary-fixed-dim/10 text-primary-container dark:text-primary-fixed-dim">
            <span className="material-symbols-outlined text-lg">psychology</span>
          </span>
          AI Reasoning &amp; Analysis
        </p>
        {showResult ? (
          <div className="flex items-center gap-2">
            {data.status === 'FALLBACK' ? (
              <Chip tone="medium">Bukan hasil AI — template otomatis</Chip>
            ) : null}
            {data.stale ? <Chip tone="neutral">Basi — data berubah</Chip> : null}
          </div>
        ) : null}
      </div>

      <div className="p-5 space-y-4">
        {data.status === 'NONE' ? (
          <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
            Dapatkan satu rekomendasi penanganan untuk debitur ini, hasil rekonsiliasi AI atas seluruh
            kontrak aktif dan riwayat perilakunya — bukan rekomendasi terpisah per kontrak.
          </p>
        ) : null}

        {data.status === 'DISABLED' ? (
          <p className="flex items-center gap-1.5 text-body-md text-on-surface-variant dark:text-surface-variant">
            <span className="material-symbols-outlined text-lg">info</span>
            Fitur AI Reasoning belum dinyalakan.
          </p>
        ) : null}

        {data.status === 'RUNNING' ? (
          <div className="flex items-center justify-between gap-3 rounded-lg bg-surface-container-high/40 dark:bg-surface-container-high/10 p-3">
            <p className="flex items-center gap-1.5 text-body-md text-on-surface-variant dark:text-surface-variant">
              <span className="material-symbols-outlined text-lg text-primary-container dark:text-primary-fixed-dim animate-spin">
                progress_activity
              </span>
              Analisa sedang diproses...
            </p>
            <button
              type="button"
              onClick={() => query.refetch()}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-outline-variant dark:border-outline-variant/30 text-label-md text-on-surface-variant dark:text-surface-variant shrink-0"
            >
              <span className="material-symbols-outlined text-base">refresh</span>
              Cek status
            </button>
          </div>
        ) : null}

        {data.status === 'FAILED' ? (
          <p className="flex items-center gap-1.5 text-body-md text-on-surface dark:text-on-background">
            <span className="material-symbols-outlined text-lg text-error">error</span>
            Gagal menghasilkan analisa AI. Silakan coba lagi.
          </p>
        ) : null}

        {data.status === 'INSUFFICIENT_DATA' ? (
          <div className="space-y-1.5">
            <p className="flex items-center gap-1.5 text-body-md font-semibold text-on-surface dark:text-on-background">
              <span className="material-symbols-outlined text-lg text-warning">info</span>
              Data belum cukup untuk analisa AI
            </p>
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
              Debitur ini {INSUFFICIENT_REASON_LABEL[data.insufficientReason ?? ''] ?? 'belum memenuhi syarat minimum data'}.
              Gunakan skor dan rekomendasi per kontrak di halaman Contract Detail sebagai acuan sementara.
            </p>
          </div>
        ) : null}

        {showResult ? (
          <div className="space-y-4">
            <p className="text-body-md text-on-surface dark:text-on-background">{data.summary}</p>

            {data.customerTreatmentStrategy ? (
              <div className="rounded-lg bg-primary-container/40 dark:bg-primary-fixed-dim/10 p-4">
                <p className="text-label-md font-semibold text-on-surface dark:text-on-background mb-1">
                  Strategi Penanganan Debitur
                </p>
                <p className="text-body-md text-on-surface dark:text-on-background">{data.customerTreatmentStrategy}</p>
              </div>
            ) : null}

            {data.keyFactors.length > 0 ? (
              <div>
                <p className="text-label-md font-semibold text-on-surface dark:text-on-background mb-2">Faktor Kunci</p>
                <ul className="list-disc list-inside space-y-1">
                  {data.keyFactors.map((factor) => (
                    <li key={factor} className="text-body-md text-on-surface-variant dark:text-surface-variant">
                      {factor}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {data.primaryNbaAction ? (
              <div>
                <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">
                  Next Best Action (Level Debitur)
                </p>
                <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-container text-on-primary-container text-label-lg font-semibold">
                  <span className="material-symbols-outlined text-lg">bolt</span>
                  {data.primaryNbaAction}
                </span>
                {data.primaryNbaRationale ? (
                  <p className="mt-2 text-body-md text-on-surface-variant dark:text-surface-variant">
                    {data.primaryNbaRationale}
                  </p>
                ) : null}
                {data.nbaAgreement === 'DIFFER' ? (
                  <div className="mt-2 flex items-start gap-2 rounded-lg bg-warning-container/40 dark:bg-warning/10 p-3">
                    <span className="material-symbols-outlined text-lg text-warning shrink-0">sync_problem</span>
                    <p className="text-body-md text-on-surface dark:text-on-background">
                      Berbeda dari rekomendasi sistem per kontrak — AI mempertimbangkan seluruh profil
                      debitur, bukan satu kontrak saja.
                    </p>
                  </div>
                ) : null}
              </div>
            ) : null}

            {sortedFocus.length > 0 ? (
              <div>
                <p className="text-label-md font-semibold text-on-surface dark:text-on-background mb-2">
                  Fokus per Kontrak
                </p>
                <div className="space-y-2">
                  {sortedFocus.map((item) => (
                    <div
                      key={item.contractNo}
                      className="flex items-start gap-3 rounded-lg border border-outline-variant dark:border-outline-variant/30 p-3"
                    >
                      <Chip tone={URGENCY_TONE[item.urgency]}>{item.urgency}</Chip>
                      <div>
                        <p className="text-label-md font-semibold text-on-surface dark:text-on-background">
                          {item.contractNo}
                        </p>
                        <p className="text-body-md text-on-surface-variant dark:text-surface-variant">{item.note}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {data.consistencyNote ? (
              <div className="flex items-start gap-2 border-t border-outline-variant dark:border-outline-variant/30 pt-3">
                <span className="material-symbols-outlined text-base text-on-surface-variant dark:text-surface-variant shrink-0">
                  link
                </span>
                <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">
                  {data.consistencyNote}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}

        {showGenerateButton ? (
          <button
            type="button"
            onClick={handleGenerate}
            disabled={isBusy || data.status === 'DISABLED'}
            className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold disabled:opacity-60"
          >
            <span className={`material-symbols-outlined text-lg ${isBusy ? 'animate-spin' : ''}`}>
              {isBusy ? 'progress_activity' : 'bolt'}
            </span>
            {isBusy
              ? 'Menganalisa...'
              : data.status === 'FAILED' || data.status === 'INSUFFICIENT_DATA'
                ? 'Coba Lagi'
                : 'Generate AI Reasoning & Analysis'}
          </button>
        ) : null}
      </div>
    </div>
  );
}
