# Restructuring Approval API

## Overview

The supervisor approval queue: lists restructuring groups awaiting a decision (`offer_status = GENERATED`, default view) plus a history tab (`OFFERED`/`REJECTED`), with **Approve** (`GENERATED → OFFERED`) and **Reject** (`GENERATED → REJECTED`, no reason required) actions.

**Backend status:** new — endpoints don't exist yet, but the underlying data does: `restructuring_recommendation_output` (already has `offer_status`, `eligibility_tier`, `eligibility_reasons`) and `restructuring_group_map` (contract_no ↔ restructure_group_id, needed for the `contractNos` column). Per the design doc, **audit logging for approve/reject should be built in the same pass as these endpoints** (closing the old TASK-59 gap), not as a follow-up — record who approved/rejected and when, likely reusing whatever audit table backs `model_governance_config` (`04-ai-intelligence.md`) if the shape fits, or a new table otherwise.

**Role & Access:** visible to every logged-in user for this phase — RBAC was explicitly deferred (see `frontend-layout-upgrade-tasks.md` TASK-A). Don't add permission gating here yet.

**Consumed by:** `src/pages/RestructuringApprovalPage.tsx`.

**Frontend files:**
- Schema: `src/domains/restructuring/restructuring.schema.ts` (shared with `08-restructuring.md` — same domain, same `restructuring_recommendation_output` source)
- API calls: `src/domains/restructuring/restructuring.api.ts`
- Hooks: `src/domains/restructuring/useRestructuringGroupsQuery.ts`, `src/domains/restructuring/useApproveRestructuringGroupMutation.ts`, `src/domains/restructuring/useRejectRestructuringGroupMutation.ts`
- Mock: `src/mocks/fixtures/restructuring.fixtures.ts`, `src/mocks/handlers/restructuring.handlers.ts` (mutates the same in-memory records `08-restructuring.md`'s endpoints read, so approving a group here is immediately reflected in that customer's "Opsi Restrukturisasi" card)

---

## `GET /restructuring-groups?status=`

**Auth required:** Yes.

**Query params**

| Param | Type | Notes |
|---|---|---|
| `status` | `GENERATED` \| `HISTORY` | `GENERATED` (default/first tab) returns groups with `offer_status = 'GENERATED'` — the approval queue. `HISTORY` (second tab) returns groups with `offer_status` in `('OFFERED', 'REJECTED')` — i.e. already decided by a supervisor. `ACCEPTED`/`EXPIRED` groups are intentionally excluded from both tabs (out of scope for this page — accepted-offer tracking belongs to Customer Detail / core-banking). |

**Success response — `200`**

```json
[
  {
    "restructureGroupId": "RG-CUST-00001-2026-07-15-1",
    "custId": "CUST-00001",
    "contractNos": ["CTR-00001-1"],
    "offerType": "REFINANCE",
    "eligibilityTier": "MANUAL_REVIEW",
    "eligibilityReasons": ["DPD 62 di luar window standar (30-180) untuk offer_type ini"],
    "npvBaseline": 3200000,
    "npvRestructured": 9800000,
    "offerStatus": "GENERATED",
    "generatedDate": "2026-07-15"
  }
]
```

| Field | Type | Notes |
|---|---|---|
| `restructureGroupId` | string | PK of `restructuring_recommendation_output`. |
| `custId` | string | Links to `/customers/:custId`. |
| `contractNos` | array of string | From `restructuring_group_map` rows for this `restructure_group_id` (>1 for `CONSOLIDATE`). |
| `offerType` | `"REFINANCE" \| "CONSOLIDATE" \| "TAKEOVER"` | |
| `eligibilityTier` | `"AUTO" \| "MANUAL_REVIEW" \| "BLOCKED"` | In practice, everything in the `GENERATED` queue is expected to be `MANUAL_REVIEW` (that's *why* it's stuck awaiting approval) — `AUTO`-tier groups should auto-progress past `GENERATED` without landing in this queue. If the backend ever surfaces an `AUTO` row here, that's worth double-checking upstream logic. |
| `eligibilityReasons` | array of string | Rendered under the tier chip. |
| `npvBaseline`, `npvRestructured` | number | Raw Rupiah amounts (not pre-formatted) — same convention as `08-restructuring.md`'s offer fields. Frontend renders `npvBaseline → npvRestructured`. |
| `offerStatus` | `"GENERATED" \| "OFFERED" \| "ACCEPTED" \| "REJECTED" \| "EXPIRED"` | Drives the history tab's status chip; not shown as a column in the `GENERATED` tab (redundant there — everything is `GENERATED`). |
| `generatedDate` | string | When the group was created. |

---

## `POST /restructuring-groups/:groupId/approve`

Transitions a group `GENERATED → OFFERED`, making it visible/respondable on the customer's "Opsi Restrukturisasi" card (`08-restructuring.md`'s `canRespond` flips to `true`).

**Auth required:** Yes.

**Request:** no body.

**Success response — `200`** — the updated group, same shape as one item of the `GET` array above, with `offerStatus: "OFFERED"`.

**Error responses**

| Status | When |
|---|---|
| `404` | Unknown `groupId`. |
| `409` | Group isn't currently `GENERATED` (e.g. already approved/rejected by someone else) — recommended for the real backend even though the frontend doesn't have a specific conflict-resolution UI for this race yet (it just shows the generic error state and the row would disappear on the next list refetch). |

**Audit requirement:** record `who` (current authenticated user) and `when` for this action — see Overview.

---

## `POST /restructuring-groups/:groupId/reject`

Transitions a group `GENERATED → REJECTED`. **No reason/note field** — this is an explicit, final product decision (per the design doc), not a placeholder to fill in later.

**Auth required:** Yes.

**Request:** no body.

**Success response — `200`** — the updated group, with `offerStatus: "REJECTED"`.

**Error responses:** same as `approve` above.

**After either action:** the frontend invalidates all `['restructuring', 'groups', *]` queries (both tabs), so the row disappears from `GENERATED` and appears in `HISTORY` on the next render without a manual page refresh.

**Audit requirement:** same as `approve` above.
