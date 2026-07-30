import { z } from 'zod';

// Mirrors app/backend/schemas/restructuring.py's RestructureOfferSchema/
// RestructuringAssessmentSchema, in camelCase per this codebase's convention.
export const offerTypeSchema = z.enum(['REFINANCE', 'CONSOLIDATE', 'TAKEOVER']);
export type OfferType = z.infer<typeof offerTypeSchema>;

export const eligibilityTierSchema = z.enum(['AUTO', 'MANUAL_REVIEW', 'BLOCKED']);
export type EligibilityTier = z.infer<typeof eligibilityTierSchema>;

export const offerStatusSchema = z.enum(['GENERATED', 'OFFERED', 'ACCEPTED', 'REJECTED', 'EXPIRED']);
export type OfferStatus = z.infer<typeof offerStatusSchema>;

export const restructureOfferSchema = z.object({
  offerType: offerTypeSchema,
  contractNos: z.array(z.string()),
  recommendedNewTenorMonths: z.number(),
  recommendedNewRate: z.number(),
  recommendedNewInstallment: z.number(),
  recoveryFromAsset: z.number(),
  npvBaseline: z.number(),
  npvRestructured: z.number(),
  // Display-only "honest" comparison — npvRestructured * recovery_score, so both sides
  // of the NPV comparison apply the same risk discount (npvBaseline is already
  // risk-adjusted; npvRestructured on its own was not, which made the raw delta
  // misleading). Backend ranking/guardrail logic still uses raw npvRestructured.
  npvRestructuredRiskAdjusted: z.number(),
  // Raw, undiscounted totals: current_installment * remaining_tenor vs
  // new_installment * new_tenor — a simpler, non-NPV comparison shown alongside.
  totalRemainingCurrent: z.number(),
  totalNewSchedule: z.number(),
  isGuardrailPassed: z.boolean(),
});
export type RestructureOffer = z.infer<typeof restructureOfferSchema>;

export const customerResponseValueSchema = z.enum(['ACCEPTED', 'REJECTED']);
export type CustomerResponseValue = z.infer<typeof customerResponseValueSchema>;

// `GET /customers/{custId}/restructuring-options` — on-demand assessment, now
// enriched by the backend with a lookup against any EXISTING persisted group
// in restructuring_recommendation_output for this customer (from a batch run
// or prior on-demand call that got approved/offered):
// - `restructureGroupId` — NULLABLE. Null means no persisted group exists yet
//   for this customer (pure preview, nothing to respond to) — most commonly
//   for BLOCKED-tier contracts, which are never persisted at all. Needed by
//   the frontend to call the customer-response endpoint when non-null.
// - `canRespond` — true only when the persisted group's offer_status is
//   OFFERED (AUTO-tier offers start there; MANUAL_REVIEW only gets there after
//   supervisor approval). Always false when restructureGroupId is null.
// - `customerResponse` — 'ACCEPTED'/'REJECTED' if the customer already
//   responded to the persisted group, else null.
export const restructuringAssessmentSchema = z.object({
  custId: z.string(),
  contractNo: z.string(),
  restructureGroupId: z.string().nullable(),
  eligibilityTier: eligibilityTierSchema,
  eligibilityReasons: z.array(z.string()),
  offers: z.array(restructureOfferSchema),
  canRespond: z.boolean(),
  customerResponse: customerResponseValueSchema.nullable(),
  source: z.string(),
});
export type RestructuringAssessment = z.infer<typeof restructuringAssessmentSchema>;

export const customerResponseResultSchema = z.object({
  restructureGroupId: z.string(),
  custId: z.string(),
  response: z.string(),
  message: z.string(),
});
export type CustomerResponseResult = z.infer<typeof customerResponseResultSchema>;

// ---- Restructuring Approval (TASK-E) — restructuring_recommendation_output rows ----
export const restructuringGroupStatusFilterSchema = z.enum(['GENERATED', 'HISTORY']);
export type RestructuringGroupStatusFilter = z.infer<typeof restructuringGroupStatusFilterSchema>;

export const restructuringGroupSchema = z.object({
  restructureGroupId: z.string(),
  custId: z.string(),
  contractNos: z.array(z.string()),
  offerType: offerTypeSchema,
  eligibilityTier: eligibilityTierSchema,
  // Single string, not an array — the backend joins multiple reasons with "; ". Split
  // on that separator in components that need a bullet list (see
  // RestructuringGroupDetailPage.tsx), don't expect an array from the API. Nullable
  // (and can be an empty string for AUTO-tier offers with no notes) per the real
  // OpenAPI contract — verified against a live backend instance.
  eligibilityReasons: z.string().nullable(),
  // Nullable per the real OpenAPI contract (verified live) — not observed null in
  // practice yet, but the backend schema allows it.
  npvBaseline: z.number().nullable(),
  npvRestructured: z.number().nullable(),
  // Same nullability as npvBaseline/npvRestructured above — see restructureOfferSchema
  // for what these represent (risk-adjusted NPV comparison + raw undiscounted totals).
  npvRestructuredRiskAdjusted: z.number().nullable(),
  totalRemainingCurrent: z.number().nullable(),
  totalNewSchedule: z.number().nullable(),
  offerStatus: offerStatusSchema,
  generatedDate: z.string(),
});
export type RestructuringGroup = z.infer<typeof restructuringGroupSchema>;

// GET /restructuring-groups is now paginated (page/page_size), same pattern as
// Customer/Contract list — `groups` + `pageInfo`, not a raw array anymore.
export const restructuringGroupPageInfoSchema = z.object({
  showingFrom: z.number(),
  showingTo: z.number(),
  totalGroups: z.number(),
  totalPages: z.number(),
});
export type RestructuringGroupPageInfo = z.infer<typeof restructuringGroupPageInfoSchema>;

export const restructuringGroupsResponseSchema = z.object({
  groups: z.array(restructuringGroupSchema),
  pageInfo: restructuringGroupPageInfoSchema,
});
export type RestructuringGroupsResponse = z.infer<typeof restructuringGroupsResponseSchema>;

// `GET /restructuring-groups/{restructure_group_id}` — single-group detail, same shape
// as a list item (TASK-7).
export const restructuringGroupDetailSchema = restructuringGroupSchema;
export type RestructuringGroupDetail = z.infer<typeof restructuringGroupDetailSchema>;

// `POST /restructuring-groups/{id}/approve|reject` — a DIFFERENT (smaller) shape than
// the list/detail item: no `contract_nos`/`eligibility_tier`/`eligibility_reasons`/
// `npv_baseline`/`npv_restructured`, plus a new `expiry_date` field. Verified against a
// live backend instance (`RestructuringGroupActionResult` in its OpenAPI schema) —
// reusing `restructuringGroupSchema` here would fail validation.
export const restructuringGroupActionResultSchema = z.object({
  restructureGroupId: z.string(),
  custId: z.string(),
  offerType: offerTypeSchema,
  offerStatus: offerStatusSchema,
  generatedDate: z.string(),
  expiryDate: z.string().nullable(),
});
export type RestructuringGroupActionResult = z.infer<typeof restructuringGroupActionResultSchema>;
