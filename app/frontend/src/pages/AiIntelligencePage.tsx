import AppLayout from '../layouts/AppLayout';
import WeightSlider from '../components/WeightSlider';
import ModelLogTable from '../components/ModelLogTable';
import ProgressBar from '../components/ProgressBar';
import AiIntelligenceSkeleton from '../components/skeletons/AiIntelligenceSkeleton';
import ErrorState from '../components/ErrorState';
import { toDisplayMessage } from '../api/apiError';
import { useWeightingParameters } from '../hooks/useWeightingParameters';
import { useModelConfigQuery } from '../domains/ai-intelligence/useModelConfigQuery';
import { useModelOperationalLogQuery } from '../domains/ai-intelligence/useModelOperationalLogQuery';

interface AiIntelligencePageProps {
  readonly className?: string;
}

export default function AiIntelligencePage({ className = '' }: AiIntelligencePageProps) {
  const configQuery = useModelConfigQuery();
  const operationalLogQuery = useModelOperationalLogQuery();
  const { parameters, updateWeight, resetToDefault, saveChanges, sumOfWeights, isSaving } = useWeightingParameters();

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

  const { modelInfo, riskThresholds, modelHealth, systemPrompt } = configQuery.data;

  return (
    <AppLayout title="Intelligence Config" searchPlaceholder="Search parameters..." badge={`Model: ${modelInfo.name}`}>
      <div className={`space-y-6 ${className}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-headline-sm font-bold text-on-surface dark:text-on-background">Model Management</h2>
            <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
              Configure weighting logic and risk thresholds for the automated recovery engine.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
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
            <button type="button" className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-on-background text-on-primary text-label-lg font-semibold">
              <span className="material-symbols-outlined text-lg">rocket_launch</span>
              Deploy to Production
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6 space-y-6">
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background">
                <span className="material-symbols-outlined text-lg">balance</span>
                Weighting Parameters
              </p>
              <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Sum of weights: {sumOfWeights}%</span>
            </div>
            {parameters.map((parameter) => (
              <WeightSlider key={parameter.label} parameter={parameter} onChange={(weight) => updateWeight(parameter.label, weight)} />
            ))}
          </div>

          <div className="space-y-4">
            <div className="border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
              <p className="flex items-center gap-2 text-label-lg font-semibold text-error mb-4">
                <span className="material-symbols-outlined text-lg">warning</span>
                Risk Thresholds
              </p>
              <label className="block mb-3">
                <span className="text-label-md text-on-surface-variant dark:text-surface-variant">Critical Level (Rp)</span>
                <div className="flex items-center gap-2 border border-outline-variant dark:border-outline-variant/30 rounded-lg px-3 py-2 mt-1">
                  <span className="text-on-surface-variant">Rp</span>
                  <input
                    type="text"
                    defaultValue={riskThresholds.criticalLevel}
                    className="bg-transparent flex-1 text-body-md text-on-surface dark:text-on-background focus:outline-none"
                  />
                </div>
              </label>
              <label className="block">
                <span className="text-label-md text-on-surface-variant dark:text-surface-variant">Escalation Trigger (Rp)</span>
                <div className="flex items-center gap-2 border border-outline-variant dark:border-outline-variant/30 rounded-lg px-3 py-2 mt-1">
                  <span className="text-on-surface-variant">Rp</span>
                  <input
                    type="text"
                    defaultValue={riskThresholds.escalationTrigger}
                    className="bg-transparent flex-1 text-body-md text-on-surface dark:text-on-background focus:outline-none"
                  />
                </div>
              </label>
              <p className="text-label-md text-on-surface-variant dark:text-surface-variant bg-secondary-container/40 dark:bg-secondary/10 rounded-lg p-3 mt-4">
                {riskThresholds.note}
              </p>
            </div>

            <div className="rounded-xl bg-primary-container text-on-primary p-5">
              <p className="text-label-lg font-semibold mb-2">Model Health</p>
              <p className="flex items-center gap-1.5 text-body-lg mb-3">
                <span className="material-symbols-outlined">check_circle</span>
                {modelHealth.status}
              </p>
              <ProgressBar value={modelHealth.progress} tone="primary" />
              <p className="text-label-md text-on-primary-container mt-3">{modelHealth.accuracyLabel}</p>
            </div>
          </div>
        </div>

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background">
              <span className="material-symbols-outlined text-lg">auto_awesome</span>
              Local LLM System Prompt
            </p>
            <span className="text-label-sm text-on-surface-variant dark:text-surface-variant">{systemPrompt.version}</span>
          </div>
          <textarea
            defaultValue={systemPrompt.content}
            rows={8}
            className="w-full bg-surface-container-low dark:bg-surface-container-high/20 border border-outline-variant dark:border-outline-variant/30 rounded-lg p-4 font-mono text-body-md text-on-surface dark:text-on-background focus:outline-none"
          />
          <div className="flex items-center justify-between mt-3">
            <p className="text-label-md text-on-surface-variant dark:text-surface-variant">{systemPrompt.affectedChannelsNote}</p>
            <button type="button" className="text-label-lg font-semibold text-primary-container dark:text-primary-fixed-dim hover:underline">
              Test Prompt Performance
            </button>
          </div>
        </div>

        <div className="bg-surface-container-lowest dark:bg-surface-container-high/10 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-6">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-4">Operational Log (Aktivitas Model)</p>
          <ModelLogTable entries={operationalLogQuery.data} />
        </div>
      </div>
    </AppLayout>
  );
}
