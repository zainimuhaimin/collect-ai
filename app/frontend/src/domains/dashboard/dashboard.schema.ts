import { z } from 'zod';

export const kpiStatSchema = z.object({
  icon: z.string(),
  label: z.string(),
  value: z.string(),
  change: z.string(),
  trend: z.enum(['up', 'down', 'flat']),
  tone: z.enum(['neutral', 'positive', 'negative']),
});
export type KpiStat = z.infer<typeof kpiStatSchema>;

export const dpdBucketSchema = z.object({
  label: z.string(),
  settled: z.number(),
  activePtp: z.number(),
  broken: z.number(),
});
export type DpdBucket = z.infer<typeof dpdBucketSchema>;

export const funnelStageSchema = z.object({
  label: z.string(),
  value: z.string(),
  percentage: z.string(),
});
export type FunnelStage = z.infer<typeof funnelStageSchema>;

export const channelEfficiencySchema = z.object({
  channel: z.string(),
  rate: z.string(),
});
export type ChannelEfficiency = z.infer<typeof channelEfficiencySchema>;

export const priorityAccountSchema = z.object({
  customerId: z.string(),
  name: z.string(),
  initials: z.string(),
  amount: z.string(),
  ambcValue: z.string(),
  ambcTier: z.enum(['High', 'Medium', 'Low']),
  lastAction: z.string(),
  lastActionDate: z.string(),
});
export type PriorityAccount = z.infer<typeof priorityAccountSchema>;

export const dashboardSummaryResponseSchema = z.object({
  kpis: z.array(kpiStatSchema),
  dpdBuckets: z.array(dpdBucketSchema),
  contactabilityFunnel: z.array(funnelStageSchema),
  channelEfficiency: channelEfficiencySchema,
  brokenPtpPriorities: z.array(priorityAccountSchema),
  syncNote: z.string(),
});
export type DashboardSummary = z.infer<typeof dashboardSummaryResponseSchema>;
