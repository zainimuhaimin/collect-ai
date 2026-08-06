import { z } from 'zod';

// GET/POST /customers/{custId}/ai-reasoning — ai-reasoning-api-upgrade-tasks.md.
// Grain-nya DEBITUR, bukan kontrak: satu hasil merekonsiliasi SEMUA kontrak
// aktif customer ini jadi satu strategi penanganan.

export const aiReasoningStatusSchema = z.enum([
  'NONE', // belum pernah digenerate
  'DISABLED', // fitur mati (AI_REASONING_ENABLED=false di backend)
  'RUNNING',
  'OK',
  'FALLBACK', // Gemini gagal — ini template rule-based, BUKAN hasil AI (harus terlihat beda di UI)
  'FAILED',
  'INSUFFICIENT_DATA', // data debitur belum cukup — BUKAN error
]);
export type AiReasoningStatus = z.infer<typeof aiReasoningStatusSchema>;

// 5 nilai nyata — HARUS sinkron dengan business_rules.py CHANNEL_RANK di
// backend (satu sumber kebenaran ada di sana, ini cermin untuk validasi UI).
export const nbaActionSchema = z.enum(['WA', 'Deskcoll', 'Visit', 'Somasi', 'Pickup']);
export type NbaAction = z.infer<typeof nbaActionSchema>;

export const perContractFocusSchema = z.object({
  contractNo: z.string(),
  urgency: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
  note: z.string(),
});
export type PerContractFocus = z.infer<typeof perContractFocusSchema>;

export const aiReasoningResponseSchema = z.object({
  status: aiReasoningStatusSchema,
  insufficientReason: z.string().nullable(),
  stale: z.boolean(),
  generatedAt: z.string().nullable(),
  promptVersion: z.string().nullable(),
  modelUsed: z.string().nullable(),
  summary: z.string().nullable(),
  customerTreatmentStrategy: z.string().nullable(),
  keyFactors: z.array(z.string()),
  primaryNbaAction: nbaActionSchema.nullable(),
  primaryNbaRationale: z.string().nullable(),
  nbaAgreement: z.enum(['AGREE', 'DIFFER']).nullable(),
  perContractFocus: z.array(perContractFocusSchema),
  consistencyNote: z.string().nullable(),
  analyzedContractNos: z.array(z.string()),
});
export type AiReasoningResponse = z.infer<typeof aiReasoningResponseSchema>;
