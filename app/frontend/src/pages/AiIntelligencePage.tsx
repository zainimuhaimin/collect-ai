import AppLayout from '../layouts/AppLayout';
import WeightSlider from '../components/WeightSlider';
import ModelLogTable from '../components/ModelLogTable';
import LlmSystemPromptCard from '../components/LlmSystemPromptCard';
import ProgressBar from '../components/ProgressBar';
import AiIntelligenceSkeleton from '../components/skeletons/AiIntelligenceSkeleton';
import ErrorState from '../components/ErrorState';
import { ApiError, toDisplayMessage } from '../api/apiError';
import { useWeightingParameters } from '../hooks/useWeightingParameters';
import { useModelConfigQuery } from '../domains/ai-intelligence/useModelConfigQuery';
import { useModelOperationalLogQuery } from '../domains/ai-intelligence/useModelOperationalLogQuery';
import { useSyncStatusQuery } from '../domains/ai-intelligence/useSyncStatusQuery';
import { useTriggerSyncMutation } from '../domains/ai-intelligence/useTriggerSyncMutation';
import { formatDateHuman, formatDateTimeHuman, formatDurationSeconds } from '../lib/format';
import type { SyncStep, SyncStepStatus } from '../domains/ai-intelligence/aiIntelligence.schema';

interface AiIntelligencePageProps {
  readonly className?: string;
}

const STEP_ICON: Record<SyncStepStatus, string> = {
  pending: 'radio_button_unchecked',
  running: 'progress_activity',
  done: 'check_circle',
  failed: 'cancel',
};

const STEP_TONE: Record<SyncStepStatus, string> = {
  pending: 'text-on-surface-variant dark:text-surface-variant',
  running: 'text-primary-container dark:text-primary-fixed-dim animate-spin',
  done: 'text-success',
  failed: 'text-error',
};

function StepRow({ step }: { readonly step: SyncStep }) {
  return (
    <div className="flex items-center gap-2 py-1.5">
      <span className={`material-symbols-outlined text-lg ${STEP_TONE[step.status]}`}>{STEP_ICON[step.status]}</span>
      <span className="text-body-md text-on-surface dark:text-on-background">{step.modelType}</span>
      <span className="text-label-sm text-on-surface-variant dark:text-surface-variant">({step.action})</span>
      {step.durationS !== null ? (
        <span className="text-label-sm text-on-surface-variant dark:text-surface-variant">
          — {formatDurationSeconds(step.durationS)}
        </span>
      ) : null}
    </div>
  );
}

export default function AiIntelligencePage({ className = '' }: AiIntelligencePageProps) {
  const configQuery = useModelConfigQuery();
  const operationalLogQuery = useModelOperationalLogQuery();
  const { parameters, updateWeight, resetToDefault, saveChanges, sumOfWeights, isSaving } = useWeightingParameters();
  const syncStatusQuery = useSyncStatusQuery();
  const triggerSyncMutation = useTriggerSyncMutation();

  const syncStatus = syncStatusQuery.data;
  const isRunning = syncStatus?.status === 'running';
  const syncButtonDisabled = isRunning || triggerSyncMutation.isPending;

  const handleSyncNow = () => {
    triggerSyncMutation.mutate(undefined, {
      onError: (error) => {
        // 409 = a sync is already in progress — treat it as "let's just watch it",
        // not as a user-facing error. useSyncStatusQuery is already polling.
        if (error instanceof ApiError && error.status === 409) {
          syncStatusQuery.refetch();
          return;
        }
      },
    });
  };

  if (configQuery.isLoading || operationalLogQuery.isLoading) {
    return (
      <AppLayout title="Intelligence Config" searchPlaceholder="Search parameters...">
        <AiIntelligenceSkeleton />
      </AppLayout>
    );
  }

  if (configQuery.isError || !configQuery.data) {
    return (
      <AppLayout title="Intelligence Config" searchPlaceholder="Search parameters...">
        <ErrorState message={toDisplayMessage(configQuery.error)} onRetry={() => configQuery.refetch()} />
      </AppLayout>
    );
  }

  if (operationalLogQuery.isError || !operationalLogQuery.data) {
    return (
      <AppLayout title="Intelligence Config" searchPlaceholder="Search parameters...">
        <ErrorState message={toDisplayMessage(operationalLogQuery.error)} onRetry={() => operationalLogQuery.refetch()} />
      </AppLayout>
    );
  }

  const { modelHealth } = configQuery.data;
  const { scoringModel } = modelHealth;

  return (
    <AppLayout
      title="Intelligence Config"
      searchPlaceholder="Search parameters..."
      badge={scoringModel?.championVersion ? `Model: ${scoringModel.championVersion}` : undefined}
    >
      <div className={`space-y-6 ${className}`}>
        {/* Sync control — top-right corner of the BODY, not the global header. */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-headline-sm font-bold text-on-surface dark:text-on-background">AI Intelligence</h2>
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
              Bobot CBS, kesehatan model scoring, dan sinkronisasi data.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <button
              type="button"
              onClick={handleSyncNow}
              disabled={syncButtonDisabled}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold disabled:opacity-60"
            >
              {syncButtonDisabled ? (
                <span className="material-symbols-outlined text-lg animate-spin">progress_activity</span>
              ) : (
                <span className="material-symbols-outlined text-lg">sync</span>
              )}
              {isRunning ? 'Syncing...' : 'Sync Now'}
            </button>
            <span className="text-label-sm text-on-surface-variant dark:text-surface-variant">
              Terakhir di-scoring: {formatDateTimeHuman(syncStatus?.lastScoredAt)}
            </span>
          </div>
        </div>

        {syncStatus && syncStatus.status !== 'idle' ? (
          <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-2">Progres Sync</p>
            {syncStatus.steps.map((step) => (
              <StepRow key={step.modelType} step={step} />
            ))}
            {syncStatus.status === 'completed' ? (
              <p className="flex items-center gap-1.5 mt-2 text-label-md text-success">
                <span className="material-symbols-outlined text-lg">check_circle</span>
                Sync selesai.
              </p>
            ) : null}
            {syncStatus.status === 'failed' ? (
              <p className="flex items-center gap-1.5 mt-2 text-label-md text-error">
                <span className="material-symbols-outlined text-lg">error</span>
                Sync gagal{syncStatus.error ? `: ${syncStatus.error}` : '.'}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6 space-y-6">
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background">
                <span className="material-symbols-outlined text-lg">balance</span>
                Weighting Parameters (Bobot CBS)
              </p>
              <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Sum of weights: {sumOfWeights}%</span>
            </div>
            {parameters.map((parameter) => (
              <WeightSlider key={parameter.label} parameter={parameter} onChange={(weight) => updateWeight(parameter.label, weight)} />
            ))}
            <div className="flex items-center gap-2 pt-2 border-t border-outline-variant dark:border-outline-variant/30">
              <button
                type="button"
                onClick={resetToDefault}
                className="px-4 py-2.5 rounded-lg border border-outline-variant dark:border-outline-variant/30 text-label-lg"
              >
                Reset to Default
              </button>
              <button
                type="button"
                onClick={saveChanges}
                disabled={isSaving}
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold disabled:opacity-60"
              >
                <span className="material-symbols-outlined text-lg">save</span>
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
              <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-3">Scoring Model Health</p>
              {scoringModel ? (
                <>
                  <p className="flex items-center gap-1.5 text-body-lg mb-3 text-on-surface dark:text-on-background">
                    <span
                      className={`material-symbols-outlined ${scoringModel.retrainTriggered ? 'text-warning' : 'text-success'}`}
                    >
                      {scoringModel.retrainTriggered ? 'warning' : 'check_circle'}
                    </span>
                    Champion {scoringModel.championVersion ?? '—'}
                  </p>
                  {scoringModel.auc !== null ? (
                    <ProgressBar value={scoringModel.auc * 100} tone="primary" title={`AUC ${scoringModel.auc.toFixed(4)}`} />
                  ) : null}
                  <p className="text-label-md text-on-surface-variant dark:text-surface-variant mt-3">
                    {scoringModel.auc !== null ? `AUC ${scoringModel.auc.toFixed(4)}` : 'AUC live belum tersedia'}
                    {' · '}
                    {scoringModel.nCriticalDrift} critical / {scoringModel.nWarningDrift} warning drift
                    {scoringModel.runDate ? ` · run terakhir ${formatDateHuman(scoringModel.runDate)}` : ''}
                  </p>
                  {scoringModel.auc === null ? (
                    // AUC di kartu ini adalah performa LIVE: skor yang sudah
                    // dikeluarkan lalu dicocokkan dengan hasil pembayaran
                    // nyata 30 hari kemudian. Jadi wajar kosong sampai ada
                    // riwayat scoring sepanjang itu — bukan tanda monitoring
                    // gagal, dan sengaja tidak diganti AUC training (itu
                    // angka cross-validation saat latih, bukan performa live).
                    <p className="text-label-sm text-on-surface-variant dark:text-surface-variant mt-1.5">
                      Butuh ~30 hari riwayat scoring untuk mengukur AUC live (skor dibandingkan
                      dengan pembayaran nyata setelahnya). Drift sudah terukur sejak run pertama.
                    </p>
                  ) : null}
                </>
              ) : (
                <p className="flex items-center gap-1.5 text-body-md text-on-surface-variant dark:text-surface-variant">
                  <span className="material-symbols-outlined text-lg">info</span>
                  Belum ada data monitoring — pipelines/weekly_mlops.py belum pernah dijalankan.
                </p>
              )}
            </div>

            <div className="border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
              <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-3">AI Reasoning Health</p>
              {modelHealth.aiReasoning.available ? (
                <p className="text-body-md text-on-surface dark:text-on-background">{modelHealth.aiReasoning.note}</p>
              ) : (
                <p className="flex items-center gap-1.5 text-body-md text-on-surface-variant dark:text-surface-variant">
                  <span className="material-symbols-outlined text-lg">info</span>
                  {modelHealth.aiReasoning.note}
                </p>
              )}
            </div>
          </div>
        </div>

        <LlmSystemPromptCard />

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Operational Log (Aktivitas Model)</p>
          <ModelLogTable entries={operationalLogQuery.data} />
        </div>
      </div>
    </AppLayout>
  );
}
