# Restructuring (Customer-Facing) API

## Overview

Powers Customer Detail's "Opsi Restrukturisasi" card: shows the customer's current restructuring eligibility/offer(s), and lets the customer accept/reject **once the offer has reached `OFFERED`** (see Notes on the `MANUAL_REVIEW` → Restructuring Approval dependency).

**Backend status:** mostly exists already — mirrors `app/backend/schemas/restructuring.py`'s `RestructuringAssessmentSchema`/`RestructureOfferSchema`/`CustomerResponseRequest`/`CustomerResponseResultSchema` and `app/backend/api/v1/routers/restructuring.py`'s two endpoints, just renamed to camelCase per this codebase's convention. One gap is called out explicitly below (`restructureGroupId`).

**Consumed by:** `src/pages/CustomerDetailPage.tsx` via `src/components/RestructuringOptionsCard.tsx`.

**Frontend files:**
- Schema: `src/domains/restructuring/restructuring.schema.ts`
- API calls: `src/domains/restructuring/restructuring.api.ts`
- Hooks: `src/domains/restructuring/useRestructuringOptionsQuery.ts`, `src/domains/restructuring/useSubmitCustomerResponseMutation.ts`
- Mock: `src/mocks/fixtures/restructuring.fixtures.ts`, `src/mocks/handlers/restructuring.handlers.ts`

This module also backs Restructuring Approval's data (`GET /restructuring-groups` etc.) — see `09-restructuring-approval.md` for those endpoints, which read from the same underlying `restructuring_recommendation_output` rows.

---

## `GET /customers/:custId/restructuring-options`

Computes (or reads back) the customer's current restructuring eligibility and offer(s).

**Auth required:** Yes.

**Success response — `200`**

```json
{
  "custId": "CUST-00001",
  "contractNo": "CTR-00001-1",
  "restructureGroupId": "RG-CUST-00001-2026-07-15-1",
  "eligibilityTier": "MANUAL_REVIEW",
  "eligibilityReasons": ["DPD 62 di luar window standar (30-180) untuk offer_type ini"],
  "offers": [
    {
      "offerType": "REFINANCE",
      "contractNos": ["CTR-00001-1"],
      "recommendedNewTenorMonths": 18,
      "recommendedNewRate": 0.145,
      "recommendedNewInstallment": 780000,
      "recoveryFromAsset": 0,
      "npvBaseline": 3200000,
      "npvRestructured": 9800000,
      "isGuardrailPassed": true
    }
  ],
  "canRespond": false,
  "customerResponse": null,
  "source": "ON_DEMAND"
}
```

| Field | Type | Notes |
|---|---|---|
| `custId`, `contractNo` | string | Echo of the assessed customer/contract. |
| `restructureGroupId` | string | **Gap vs. the real backend today:** `app/backend/schemas/restructuring.py`'s `RestructuringAssessmentSchema` (the on-demand assessment) does **not** currently return a `restructure_group_id` — but `POST .../customer-response` is path-scoped by one. Before wiring the frontend to a real backend, either (a) have the on-demand assessment return the `restructure_group_id` of whichever persisted `restructuring_recommendation_output` row it corresponds to (likely the latest batch-generated one for this contract), or (b) change the response endpoint's contract. Flag this to whoever owns the real backend integration. |
| `eligibilityTier` | `"AUTO" \| "MANUAL_REVIEW" \| "BLOCKED"` | Same semantics as the backend docstring: `AUTO` = offers ready to present immediately; `MANUAL_REVIEW` = offers computed but need supervisor approval first (see `09-restructuring-approval.md`); `BLOCKED` = contract data invalid or already restructured, `offers` always empty. |
| `eligibilityReasons` | array of string | Empty for `AUTO`. Human-readable reasons for `MANUAL_REVIEW`/`BLOCKED`. |
| `offers` | array | Same shape as `RestructureOfferSchema`, camelCased (see field table below). Empty only for `BLOCKED`. |
| `canRespond` | boolean | **Mock/UI-state addition, not in the raw backend schema.** `true` once the underlying group's `offer_status` has reached `OFFERED` (i.e. it's actually been presented to the customer — `AUTO`-tier offers typically reach this immediately; `MANUAL_REVIEW`-tier offers only get there after Restructuring Approval's Approve action). The real backend should compute this the same way: `offer_status === 'OFFERED'`. |
| `customerResponse` | `"ACCEPTED" \| "REJECTED" \| null` | **Mock/UI-state addition.** `null` until the customer has responded; the frontend uses this (rather than re-deriving it from `offer_status`) to show an "already responded, buttons disabled" state. Backend equivalent: whether `restructuring_history.customer_response` is set for this group. |
| `offerType` (per offer) | `"REFINANCE" \| "CONSOLIDATE" \| "TAKEOVER"` | |
| `contractNos` (per offer) | array of string | >1 entry only for `CONSOLIDATE`. |
| `recommendedNewTenorMonths` | number | |
| `recommendedNewRate` | number, decimal fraction | `0.1376` = 13.76% p.a. — **raw backend convention**, not pre-formatted or percent-scaled (contrast with Contract's `interestRate`, which *is* percent-scaled — see `07-contract.md`). Frontend formats with `formatPercentFromDecimal` (`src/lib/format.ts`). |
| `recommendedNewInstallment`, `npvBaseline`, `npvRestructured`, `recoveryFromAsset` | number | Raw Rupiah amounts (not pre-formatted strings, unlike Customer/Contract/Dashboard) — frontend formats with `formatRupiah`. |
| `isGuardrailPassed` | boolean | Always `true` in practice — offers failing the guardrail (`npvRestructured <= npvBaseline`) are filtered out before reaching this response. |
| `source` | string | `"ON_DEMAND"` today; reserved for `"BATCH"` per the backend schema. |

**Error responses**

| Status | When |
|---|---|
| `404` | `custId` has no active contract to assess. |

---

## `POST /customers/:custId/restructuring-options/:restructureGroupId/customer-response`

Records the customer's accept/reject decision on an `OFFERED` group. **Separate from Restructuring Approval's approve/reject** (`09-restructuring-approval.md`), which governs the earlier `GENERATED → OFFERED` supervisor transition.

**Auth required:** Yes.

**Request body**

```json
{ "response": "ACCEPTED" }
```

| Field | Type | Notes |
|---|---|---|
| `response` | `"ACCEPTED" \| "REJECTED"` | Case-insensitive per the backend schema; frontend always sends uppercase. |

**Success response — `200`**

```json
{
  "restructureGroupId": "RG-CUST-00003-2026-07-10-1",
  "custId": "CUST-00003",
  "response": "ACCEPTED",
  "message": "Respons customer tercatat"
}
```

**After a successful response:** the frontend invalidates/refetches `GET .../restructuring-options` for this customer, so the card should immediately show the "already responded" disabled state.

**Error responses**

| Status | When |
|---|---|
| `403` | `restructureGroupId` doesn't belong to `custId`. |
| `404` | `custId` or `restructureGroupId` not found. |
| `409` | Group isn't `OFFERED` yet (still `GENERATED`) or has already been responded to. The frontend's `canRespond`/`customerResponse` fields exist specifically so the UI never attempts a request that would hit this — but the backend should still enforce it server-side. |
| `410` | Past `expiry_date`. The frontend doesn't currently render a distinct "expired" message for this — a good follow-up once expiry becomes a real scenario to test against. |

**Note on execution:** per the backend router's own docs, accepting a `REFINANCE`/`CONSOLIDATE`/`TAKEOVER` offer here does **not** itself originate a new contract — a separate core-banking process (`app/core-banking/originator.py`) watches for `offer_status = 'ACCEPTED'` and disburses independently.
