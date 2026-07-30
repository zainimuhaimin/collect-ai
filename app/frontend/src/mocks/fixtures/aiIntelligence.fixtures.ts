import {
  modelConfigResponseSchema,
  modelOperationalLogResponseSchema,
  type ModelConfig,
  type ModelLogEntry,
  type WeightParameter,
  type SyncStatusResponse,
  type SyncStep,
} from '../../domains/ai-intelligence/aiIntelligence.schema';

export const modelConfigFixture: ModelConfig = {
  // Phase 1 (Bobot CBS) — mirrors `settings.py`'s WEIGHT_PAYMENT_RATE/WEIGHT_PTP_RELIABILITY/
  // WEIGHT_INTERACTION/WEIGHT_DELAY_SCORE (0.30/0.25/0.20/0.25), which drive
  // `customer_behavioral_standing.behavioral_grade`.
  cbsWeights: [
    { label: 'WEIGHT_PAYMENT_RATE', weight: 30, description: 'Seberapa besar pengaruh rajin bayar tepat waktu terhadap grade perilaku.' },
    { label: 'WEIGHT_PTP_RELIABILITY', weight: 25, description: 'Seberapa besar pengaruh konsistensi menepati janji bayar.' },
    { label: 'WEIGHT_INTERACTION', weight: 20, description: 'Seberapa besar pengaruh responsivitas saat dihubungi.' },
    { label: 'WEIGHT_DELAY_SCORE', weight: 25, description: 'Seberapa besar pengaruh tren keterlambatan pembayaran.' },
  ],
  modelHealth: {
    scoringModel: {
      runDate: '2026-07-21',
      auc: 0.88,
      calibrationGap: 0.02,
      nCriticalDrift: 0,
      nWarningDrift: 1,
      retrainTriggered: false,
      championVersion: 'v1',
    },
    aiReasoning: {
      available: false,
      note: 'Belum tersedia — menunggu ai_reasoning_output (lihat ai-reasoning-api-upgrade-tasks.md).',
    },
  },
};

export const modelOperationalLogFixture: ModelLogEntry[] = [
  { timestamp: '2026-07-24 14:22:10', action: 'Payment Rate Weight Adjustment', user: 'admin_irwan', status: 'Success' },
  { timestamp: '2026-07-23 12:05:45', action: 'Delay Score Weight Adjustment', user: 'admin_irwan', status: 'Success' },
  { timestamp: '2026-07-22 09:12:00', action: 'Model Retraining Start', user: 'data_sci_team', status: 'In Progress' },
];

if (import.meta.env.DEV) {
  modelConfigResponseSchema.parse(modelConfigFixture);
  modelOperationalLogResponseSchema.parse(modelOperationalLogFixture);
}

// Mutable in-memory store so the PUT handler can persist edits across refetches within
// a dev session, and so a new audit-log row shows up after a save (mirrors what a real
// backend would do). Resets on page reload — that's fine for a mock.
export function applyWeightingParametersUpdate(next: WeightParameter[]): WeightParameter[] {
  modelConfigFixture.cbsWeights = next;
  modelOperationalLogFixture.unshift({
    timestamp: new Date().toISOString(),
    action: 'Payment Rate Weight Adjustment',
    user: 'you (mock session)',
    status: 'Success',
  });
  return next;
}

// ---- Sync Now (TASK-9) — simple in-memory state machine so the mock behaves
// reasonably if MSW is ever re-enabled for local dev without a DB. Each poll of
// getSyncStatus() advances one step, eventually reaching "completed".
const SYNC_STEP_ORDER: SyncStep['modelType'][] = ['recovery', 'self_cure', 'roll_forward', 'ptp_success', 'daily_scoring'];

let lastScoredAt: string | null = '2026-07-21T17:07:00';
let syncState: SyncStatusResponse = {
  status: 'idle',
  startedAt: null,
  finishedAt: null,
  steps: SYNC_STEP_ORDER.map((modelType) => ({
    modelType,
    action: modelType === 'daily_scoring' ? 'score' : 'train_then_score',
    status: 'pending',
  })),
  lastScoredAt,
  error: null,
};

export function getSyncStatusFixture(): SyncStatusResponse {
  return syncState;
}

export function startSyncFixture(): { ok: true; jobId: string } | { ok: false; status: 409 } {
  if (syncState.status === 'running') {
    return { ok: false, status: 409 };
  }
  syncState = {
    status: 'running',
    startedAt: new Date().toISOString(),
    finishedAt: null,
    steps: SYNC_STEP_ORDER.map((modelType, index) => ({
      modelType,
      action: modelType === 'daily_scoring' ? 'score' : 'train_then_score',
      status: index === 0 ? 'running' : 'pending',
    })),
    lastScoredAt,
    error: null,
  };
  return { ok: true, jobId: `job-${Date.now()}` };
}

// Advances the mock sync state machine by one step per call — simulates progress
// across successive status polls.
export function advanceSyncFixture(): SyncStatusResponse {
  if (syncState.status !== 'running') return syncState;

  const runningIndex = syncState.steps.findIndex((step) => step.status === 'running');
  const nextSteps = syncState.steps.map((step) => ({ ...step }));
  if (runningIndex >= 0) {
    nextSteps[runningIndex].status = 'done';
    if (runningIndex + 1 < nextSteps.length) {
      nextSteps[runningIndex + 1].status = 'running';
      syncState = { ...syncState, steps: nextSteps };
    } else {
      lastScoredAt = new Date().toISOString();
      syncState = {
        ...syncState,
        steps: nextSteps,
        status: 'completed',
        finishedAt: new Date().toISOString(),
        lastScoredAt,
      };
    }
  }
  return syncState;
}
