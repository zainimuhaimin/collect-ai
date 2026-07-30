import { z } from 'zod';

// Mirrors the REAL `GET /dashboard/summary` backend response (snake_case wire shape,
// e.g. `total_outstanding`, `dpd_buckets`) — this schema is written in camelCase per
// this codebase's convention (see customer.schema.ts / contract.schema.ts) because
// `dashboard.api.ts` runs the raw JSON through `snakeToCamelDeep` (api/caseTransform.ts)
// before Zod ever sees it. Replaces an earlier, fictitious contract (invented KPIs like
// "PTP Success Rate"/"Avg AI Confidence", a 4-stage contactability funnel, a single
// best-channel object, etc.) that had no real backend source.

// ---- KPIs — exactly these 4, no `change`/`trend`/`icon` (no backend source for those) ----
export const dashboardKpisSchema = z.object({
  totalOutstanding: z.number(),
  activeDelinquentAccounts: z.number(),
  // Fraction (0.35 = 35%), NOT a percent number — format with formatPercentFromDecimal.
  // KEPT / (KEPT + BROKEN) over lkp_interaction.ptp_status, trailing window set by the
  // backend — unrelated to payment_history.self_cure_flag (the old, now-removed metric).
  ptpKeepRate: z.number(),
  manualReviewPending: z.number(),
});
export type DashboardKpis = z.infer<typeof dashboardKpisSchema>;

// ---- DPD buckets — always exactly 4 rows, backend sends an authoritative `total` ----
export const dpdBucketSchema = z.object({
  bucket: z.enum(['C0', 'C1', 'C2', 'C3+']),
  settled: z.number(),
  activePtp: z.number(),
  broken: z.number(),
  total: z.number(),
});
export type DpdBucket = z.infer<typeof dpdBucketSchema>;

// ---- Channel efficiency — variable-length list, already sorted desc by backend ----
export const channelEfficiencyItemSchema = z.object({
  treatmentType: z.string(),
  contactSuccessRate: z.number(),
});
export type ChannelEfficiencyItem = z.infer<typeof channelEfficiencyItemSchema>;

// NOTE: backend still sends `contactability_funnel` and `restructuring_pipeline_snapshot`
// in the raw response — dropped here intentionally (not parsed/consumed), per product
// decision to remove those 2 widgets from the Dashboard (superseded by Risk Segment
// Distribution shown as percentages). Zod silently strips unlisted keys, so this is
// safe even though the backend contract hasn't changed.

// ---- Risk segment distribution — dict, keys can be any subset of the 4 risk segments ----
// Kept as a loose string->number record (rather than z.record(riskSegmentSchema, ...))
// since the backend doesn't guarantee all 4 keys are always present; consumers should
// validate/lookup individual keys against `riskSegmentSchema` themselves.
export const riskSegmentDistributionSchema = z.record(z.string(), z.number());
export type RiskSegmentDistribution = z.infer<typeof riskSegmentDistributionSchema>;

export const dashboardSummaryResponseSchema = z.object({
  kpis: dashboardKpisSchema,
  dpdBuckets: z.array(dpdBucketSchema),
  channelEfficiency: z.array(channelEfficiencyItemSchema),
  riskSegmentDistribution: riskSegmentDistributionSchema,
  syncNote: z.string(),
});
export type DashboardSummary = z.infer<typeof dashboardSummaryResponseSchema>;
