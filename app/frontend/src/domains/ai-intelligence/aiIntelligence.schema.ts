import { z } from 'zod';

export const modelInfoSchema = z.object({
  name: z.string(),
  weightingSumLabel: z.string(),
});
export type ModelInfo = z.infer<typeof modelInfoSchema>;

export const weightParameterSchema = z.object({
  label: z.string(),
  weight: z.number(),
  description: z.string(),
});
export type WeightParameter = z.infer<typeof weightParameterSchema>;

export const riskThresholdsSchema = z.object({
  criticalLevel: z.string(),
  escalationTrigger: z.string(),
  note: z.string(),
});
export type RiskThresholds = z.infer<typeof riskThresholdsSchema>;

export const modelHealthSchema = z.object({
  status: z.string(),
  accuracyLabel: z.string(),
  progress: z.number(),
});
export type ModelHealth = z.infer<typeof modelHealthSchema>;

export const systemPromptSchema = z.object({
  version: z.string(),
  content: z.string(),
  affectedChannelsNote: z.string(),
});
export type SystemPrompt = z.infer<typeof systemPromptSchema>;

export const modelConfigResponseSchema = z.object({
  modelInfo: modelInfoSchema,
  weightingParameters: z.array(weightParameterSchema),
  riskThresholds: riskThresholdsSchema,
  modelHealth: modelHealthSchema,
  systemPrompt: systemPromptSchema,
});
export type ModelConfig = z.infer<typeof modelConfigResponseSchema>;

export const modelLogEntrySchema = z.object({
  timestamp: z.string(),
  action: z.string(),
  user: z.string(),
  status: z.enum(['Success', 'In Progress', 'Failed']),
});
export type ModelLogEntry = z.infer<typeof modelLogEntrySchema>;

export const modelOperationalLogResponseSchema = z.array(modelLogEntrySchema);

export const saveWeightingParametersResponseSchema = z.array(weightParameterSchema);
