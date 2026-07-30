import { z } from 'zod';
import { riskSegmentSchema } from '../shared/riskSegment';

// ---- Contract list (TASK-D) — same filter semantics as Customer, but per-row ----
// `high_amount` was renamed to `high_priority` by the backend (see customer.schema.ts).
export const contractFilterSchema = z.enum(['all', 'dpd_30_plus', 'high_priority', 'broken_ptp', 'high_ambc']);
export type ContractFilter = z.infer<typeof contractFilterSchema>;

export const contractListItemSchema = z.object({
  contractNo: z.string(),
  custId: z.string(),
  custName: z.string(),
  productType: z.string(),
  dpdCurrent: z.number(),
  outstanding: z.string(),
  riskSegment: riskSegmentSchema,
});
export type ContractListItem = z.infer<typeof contractListItemSchema>;

export const contractListPageInfoSchema = z.object({
  showingFrom: z.number(),
  showingTo: z.number(),
  totalContracts: z.number(),
  totalPages: z.number(),
});
export type ContractListPageInfo = z.infer<typeof contractListPageInfoSchema>;

export const contractListResponseSchema = z.object({
  contracts: z.array(contractListItemSchema),
  pageInfo: contractListPageInfoSchema,
});
export type ContractListResponse = z.infer<typeof contractListResponseSchema>;

// ---- Contract detail — FLAT shape, matches real backend ContractDetailSchema
// exactly (schemas/contract.py) — no nested "summary"/"outstandingBreakdown"
// grouping, and most amount fields are raw numbers (not pre-formatted strings)
// — format them at render time with formatRupiah/formatPercentFromDecimal.
export const outstandingBreakdownSchema = z.object({
  principal: z.number(),
  interest: z.number(),
  total: z.number(),
});
export type OutstandingBreakdown = z.infer<typeof outstandingBreakdownSchema>;

export const contractAiScoringSchema = z.object({
  recoveryScore: z.number(),
  riskSegment: riskSegmentSchema.nullable(),
  selfCureProbability: z.number(),
  rollForwardRisk: z.number(),
  ptpSuccessProbability: z.number(),
  nbaRecommendation: z.string().nullable(),
  confidenceLevel: z.number(),
  scoringDate: z.string().nullable(),
});
export type ContractAiScoring = z.infer<typeof contractAiScoringSchema>;

export const paymentHistoryEntrySchema = z.object({
  dueDate: z.string().nullable(),
  actualPayDate: z.string().nullable(),
  paymentAmount: z.number(),
  payStatus: z.string().nullable(),
  delayDays: z.number().nullable(),
  recoverySource: z.string().nullable(),
});
export type PaymentHistoryEntry = z.infer<typeof paymentHistoryEntrySchema>;

export const contractRestructuringStatusSchema = z
  .object({
    restructureGroupId: z.string(),
    offerStatus: z.string(),
    eligibilityTier: z.string(),
  })
  .nullable();
export type ContractRestructuringStatus = z.infer<typeof contractRestructuringStatusSchema>;

export const contractDetailSchema = z.object({
  contractNo: z.string(),
  custId: z.string(),
  custName: z.string(),
  productType: z.string(),
  cycle: z.string().nullable(),
  prevCycle: z.string().nullable(),
  closedViaRestructure: z.boolean(),
  newContractNo: z.string().nullable(),
  loanAmount: z.number(),
  installmentAmount: z.number(),
  // Raw decimal fraction (0.2848 = 28.48% p.a.) — same convention as the
  // restructuring domain's recommendedNewRate. Format with
  // formatPercentFromDecimal, NOT formatPercent.
  interestRate: z.number(),
  maturityDate: z.string().nullable(),
  remainingTenorMonths: z.number(),
  dpdCurrent: z.number(),
  overdueInstallmentCount: z.number(),
  lateFeeAmount: z.number(),
  ambc: z.number(),
  outstanding: outstandingBreakdownSchema,
  aiScoring: contractAiScoringSchema.nullable(),
  paymentHistory: z.array(paymentHistoryEntrySchema),
  restructuringStatus: contractRestructuringStatusSchema,
});
export type ContractDetail = z.infer<typeof contractDetailSchema>;

// ---- Activity log — ONE endpoint (`GET /contracts/:contractNo/activity-log`), TWO
// consumers: Contract Detail's own timeline section, and Customer Detail's per-contract
// expand. Shape mirrors the old customer-level timeline entry (now retired).
export const activityLogEntrySchema = z.object({
  id: z.string(),
  icon: z.string(),
  title: z.string(),
  // Nullable — backend emits null when the underlying lkp_interaction.action_date is
  // null (see contract_service.py).
  timestamp: z.string().nullable(),
  // Optional — backend does not always send this field.
  description: z.string().optional(),
  tone: z.enum(['default', 'danger']),
  meta: z
    .object({
      label: z.string(),
      value: z.string(),
      tone: z.enum(['success', 'danger']),
    })
    .optional(),
});
export type ActivityLogEntry = z.infer<typeof activityLogEntrySchema>;

export const activityLogResponseSchema = z.array(activityLogEntrySchema);
