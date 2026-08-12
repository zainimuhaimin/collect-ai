import { z } from 'zod';

// Phase 1 (Bobot CBS) only — the 4 real customer_behavioral_standing weighting
// constants (WEIGHT_PAYMENT_RATE/WEIGHT_PTP_RELIABILITY/WEIGHT_INTERACTION/
// WEIGHT_DELAY_SCORE). Risk & Sub-model Thresholds and Restructuring Policy
// governance were explicitly dropped from this phase's scope per the design doc.
export const weightParameterSchema = z.object({
  label: z.string(),
  weight: z.number(),
  description: z.string(),
});
export type WeightParameter = z.infer<typeof weightParameterSchema>;

// Health of the scoring model (`model_monitoring_log`: AUC, drift status) —
// matches backend's ScoringModelHealthSchema exactly (schemas/governance.py).
// null as a WHOLE (see modelHealthSchema below) when model_monitoring_log has
// never had a row — that's written only by weekly_mlops.py, not daily_scoring.py.
export const scoringModelHealthSchema = z.object({
  runDate: z.string().nullable(),
  auc: z.number().nullable(),
  calibrationGap: z.number().nullable(),
  nCriticalDrift: z.number(),
  nWarningDrift: z.number(),
  retrainTriggered: z.boolean(),
  championVersion: z.string().nullable(),
});
export type ScoringModelHealth = z.infer<typeof scoringModelHealthSchema>;

// AI Reasoning health (`ai_reasoning_output.status` OK/FALLBACK/FAILED ratio) has no
// backing table yet (tracked in ai-reasoning-api-upgrade-tasks.md) — render a muted
// "not available yet" state rather than a fake progress bar.
export const aiReasoningHealthSchema = z.object({
  available: z.boolean(),
  note: z.string(),
});
export type AiReasoningHealth = z.infer<typeof aiReasoningHealthSchema>;

export const modelHealthSchema = z.object({
  scoringModel: scoringModelHealthSchema.nullable(),
  aiReasoning: aiReasoningHealthSchema,
});
export type ModelHealth = z.infer<typeof modelHealthSchema>;

// Matches backend's ModelConfigResponse exactly (schemas/governance.py) —
// no `modelInfo` field exists on the real backend, don't invent one.
export const modelConfigResponseSchema = z.object({
  cbsWeights: z.array(weightParameterSchema),
  modelHealth: modelHealthSchema,
});
export type ModelConfig = z.infer<typeof modelConfigResponseSchema>;

// GET /ai-intelligence/llm-system-prompt — teks persis yang dikirim sebagai
// `system_instruction` ke Gemini di setiap panggilan AI Reasoning. Read-only
// untuk saat ini (lihat komentar LlmSystemPromptSchema di backend).
export const llmSystemPromptResponseSchema = z.object({
  promptVersion: z.string(),
  systemInstruction: z.string(),
});
export type LlmSystemPrompt = z.infer<typeof llmSystemPromptResponseSchema>;

// `status` bukan enum terpusat di backend (schemas/governance.py: `status: str`) —
// setiap action-type menulis vocab statusnya sendiri ke `detail->>'status'`:
// WEIGHTING_UPDATE/MODEL_SYNC pakai Success/In Progress/Failed, AI_REASONING_GENERATE
// pakai status ai_reasoning_output (OK/FALLBACK/FAILED/INSUFFICIENT_DATA) — lihat
// ai_reasoning_service.py::_log_audit. Enum di sini HARUS mencakup superset semuanya.
export const modelLogEntrySchema = z.object({
  timestamp: z.string(),
  action: z.string(),
  user: z.string().nullable(),
  status: z.enum(['Success', 'In Progress', 'Failed', 'OK', 'FALLBACK', 'INSUFFICIENT_DATA']),
});
export type ModelLogEntry = z.infer<typeof modelLogEntrySchema>;

export const modelOperationalLogResponseSchema = z.array(modelLogEntrySchema);

export const saveWeightingParametersResponseSchema = z.array(weightParameterSchema);

// ---- Sync Now (TASK-9) — `POST /ai-intelligence/sync` + `GET /ai-intelligence/sync/status` ----
export const syncTriggerResponseSchema = z.object({
  jobId: z.string(),
  status: z.string(),
});
export type SyncTriggerResponse = z.infer<typeof syncTriggerResponseSchema>;

export const syncStepStatusSchema = z.enum(['pending', 'running', 'done', 'failed']);
export type SyncStepStatus = z.infer<typeof syncStepStatusSchema>;

export const syncStepSchema = z.object({
  modelType: z.string(),
  action: z.string(),
  status: syncStepStatusSchema,
  // TASK-P1: durasi per step (mis. "training 42 detik") — None sampai step
  // itu mulai/selesai berjalan.
  startedAt: z.string().nullable(),
  durationS: z.number().nullable(),
});
export type SyncStep = z.infer<typeof syncStepSchema>;

export const syncStatusResponseSchema = z.object({
  status: z.enum(['idle', 'running', 'completed', 'failed']),
  startedAt: z.string().nullable(),
  finishedAt: z.string().nullable(),
  steps: z.array(syncStepSchema),
  lastScoredAt: z.string().nullable(),
  error: z.string().nullable(),
});
export type SyncStatusResponse = z.infer<typeof syncStatusResponseSchema>;
