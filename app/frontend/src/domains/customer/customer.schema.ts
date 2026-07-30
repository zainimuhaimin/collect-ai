import { z } from 'zod';
import { riskSegmentSchema } from '../shared/riskSegment';

// 360°-view customer detail. Mirrors `ai_intelligence_output` (recoveryScore,
// riskSegment, selfCureProbability, rollForwardRisk, ptpSuccessProbability,
// nbaRecommendation) joined with `customer_behavioral_standing` (behavioralGrade,
// bListStatus, restructureCount, activeContractCount) by `cust_id`. Replaces the old
// invented shape entirely (riskTier/ptpHistory/ptpMonths/verified/balanceChange/
// targetNbaAction/aiJustification all had no real backend source per the design doc's
// gap analysis and are gone for good, not just renamed).
export const customerDetailSchema = z.object({
  custId: z.string(),
  name: z.string(),
  initials: z.string(),
  outstandingBalance: z.string(),
  // Nullable — no ai_intelligence_output row yet (fresh-demo / never-scored customer).
  riskSegment: riskSegmentSchema.nullable(),
  riskScore: z.number(),
  recoveryScore: z.number(),
  selfCureProbability: z.number(),
  rollForwardRisk: z.number(),
  ptpSuccessProbability: z.number(),
  nbaRecommendation: z.string().nullable(),
  behavioralGrade: z.string(),
  bListStatus: z.enum(['Y', 'N']),
  restructureCount: z.number(),
  activeContractCount: z.number(),
});
export type CustomerDetail = z.infer<typeof customerDetailSchema>;

// ---- Customer list (TASK-C) ----
// `high_amount` was renamed to `high_priority` by the backend (same underlying
// semantics — it already filtered on the customer-level `priority` field, not a raw
// amount threshold; the old name was just misleading).
export const customerFilterSchema = z.enum(['all', 'dpd_30_plus', 'high_priority', 'broken_ptp', 'high_ambc']);
export type CustomerFilter = z.infer<typeof customerFilterSchema>;

export const customerPrioritySchema = z.enum(['Medium', 'High', 'Critical']);
export type CustomerPriority = z.infer<typeof customerPrioritySchema>;

// `priority` is now the MAX priority across the customer's active contracts (computed
// server-side) rather than tied to one arbitrary contract — consumed as-is here.
export const customerListItemSchema = z.object({
  custId: z.string(),
  name: z.string(),
  activeContractCount: z.number(),
  behavioralGrade: z.string(),
  bListStatus: z.string(),
  priority: customerPrioritySchema,
});
export type CustomerListItem = z.infer<typeof customerListItemSchema>;

export const customerListPageInfoSchema = z.object({
  showingFrom: z.number(),
  showingTo: z.number(),
  totalCustomers: z.number(),
  totalPages: z.number(),
});
export type CustomerListPageInfo = z.infer<typeof customerListPageInfoSchema>;

export const customerListResponseSchema = z.object({
  customers: z.array(customerListItemSchema),
  pageInfo: customerListPageInfoSchema,
});
export type CustomerListResponse = z.infer<typeof customerListResponseSchema>;

// ---- Customer's contracts (lightweight, powers the "Kontrak Milik Customer Ini" list) ----
export const customerContractSummarySchema = z.object({
  contractNo: z.string(),
  productType: z.string(),
  dpdCurrent: z.number(),
  outstanding: z.string(),
  // Nullable — same fresh-demo/never-scored gap as customerDetailSchema.riskSegment.
  riskSegment: riskSegmentSchema.nullable(),
});
export type CustomerContractSummary = z.infer<typeof customerContractSummarySchema>;

export const customerContractsResponseSchema = z.array(customerContractSummarySchema);
