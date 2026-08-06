# Contract API

## Overview

Covers the paginated/filterable contract list, the full Contract Detail view (7 sections: summary, outstanding breakdown, AI scoring, payment history, activity log, restructuring status), and the activity-log endpoint shared with Customer Detail's per-contract expand.

**Backend status:** maps directly onto existing tables:
- `contract_snapshot` → list columns + most of the "Ringkasan Kontrak" card.
- `payment_history` → "Riwayat Pembayaran" table.
- `ai_intelligence_output` (PK `contract_no`) → "AI Scoring" card, no aggregation needed (unlike Customer Detail, which has to pick a "primary" contract — Contract Detail is already scoped to one).
- `lkp_interaction` → activity log entries + the `broken_ptp` filter.
- `restructuring_recommendation_output` / `restructuring_group_map` → "Status Restrukturisasi" card (read-only here — see Notes).

**Consumed by:** `src/pages/ContractListPage.tsx`, `src/pages/ContractDetailPage.tsx`, and `src/components/CustomerContractsList.tsx` (Customer Detail's expandable contract rows, via the activity-log endpoint only).

**Frontend files:**
- Schema: `src/domains/contract/contract.schema.ts`
- API calls: `src/domains/contract/contract.api.ts`
- Hooks: `src/domains/contract/useContractListQuery.ts`, `src/domains/contract/useContractDetailQuery.ts`, `src/domains/contract/useContractActivityLogQuery.ts`
- Mock: `src/mocks/fixtures/contract.fixtures.ts`, `src/mocks/handlers/contract.handlers.ts`

---

## `GET /contracts`

Paginated, filterable, searchable contract list. Same filter/pagination shape as `GET /customers` (`02-customer.md`), but every filter here is evaluated **per-row** (a contract either matches or doesn't — no "has a related X" indirection like Customer's `broken_ptp`/`high_ambc`).

**Auth required:** Yes.

**Query params**

| Param | Type | Notes |
|---|---|---|
| `filter` | `all` \| `dpd_30_plus` \| `high_amount` \| `broken_ptp` \| `high_ambc` | See table below. |
| `search` | string | Case-insensitive substring match against `contractNo`, `custId`, or customer name. |
| `page` | number | 1-indexed. |
| `pageSize` | number | Rows per page (frontend currently always sends `10`). |

**Filter semantics**

| Filter | Condition |
|---|---|
| `all` | No filter. |
| `dpd_30_plus` | `contract_snapshot.dpd_current >= 30`. |
| `high_amount` | `prnc_ots + intr_ots >= <threshold>` (mock uses `Rp 10.000.000` — confirm the real cutoff with product; should probably match Customer's `high_amount` semantics for consistency, even though Customer's is priority-based). |
| `broken_ptp` | This contract's latest `lkp_interaction.ptp_status = 'BROKEN'`. |
| `high_ambc` | `contract_snapshot.ambc >= <threshold>` (mock uses `Rp 10.000.000`, same value as Customer's `high_ambc` for consistency — should be the same constant on the backend). |

**Success response — `200`**

```json
{
  "contracts": [
    {
      "contractNo": "CTR-00001-1",
      "custId": "CUST-00001",
      "custName": "Budi Pratama Sitorus",
      "productType": "Personal Loan",
      "dpdCurrent": 62,
      "outstanding": "Rp 12.450.000",
      "riskSegment": "Cannot Pay"
    }
  ],
  "pageInfo": { "showingFrom": 1, "showingTo": 10, "totalContracts": 23, "totalPages": 3 }
}
```

| Field | Type | Notes |
|---|---|---|
| `contracts[].contractNo` | string | Primary identifier, links to `/contracts/:contractNo`. |
| `contracts[].custId` | string | Links to `/customers/:custId`. |
| `contracts[].custName` | string | Denormalized onto this row so the list doesn't need a second round-trip per row. |
| `contracts[].productType` | string | e.g. `"Personal Loan"`, `"KPR"`, `"Multiguna"`, `"Kartu Kredit"`. |
| `contracts[].dpdCurrent` | number | From `contract_snapshot.dpd_current`. |
| `contracts[].outstanding` | string | **Pre-formatted**, `prnc_ots + intr_ots`. |
| `contracts[].riskSegment` | `"Cannot Pay" \| "Self Cure" \| "Won't Pay"` | Displayed as-is in a chip. |
| `pageInfo` | object | Same shape/semantics as `02-customer.md`'s, with `totalContracts` instead of `totalCustomers`. |

---

## `GET /contracts/:contractNo`

Full contract detail — everything needed for all 7 detail-page sections except the activity log (separate endpoint, see below) and restructuring actions (there are none here — see Notes).

**Auth required:** Yes.

**Success response — `200`**

```json
{
  "contractNo": "CTR-00001-1",
  "custId": "CUST-00001",
  "custName": "Budi Pratama Sitorus",
  "productType": "Personal Loan",
  "cycle": "C2",
  "closedViaRestructure": false,
  "summary": {
    "loanAmount": "Rp 18.000.000",
    "installmentAmount": "Rp 1.650.000",
    "interestRate": 13.76,
    "maturityDate": "2027-04-10",
    "remainingTenorMonths": 9,
    "dpdCurrent": 62,
    "overdueInstallmentCount": 3,
    "lateFeeAmount": "Rp 185.000",
    "ambc": 12400000,
    "prevCycle": "C1"
  },
  "outstandingBreakdown": {
    "principalOutstanding": "Rp 9.800.000",
    "interestOutstanding": "Rp 2.650.000",
    "totalOutstanding": "Rp 12.450.000"
  },
  "aiScoring": {
    "recoveryScore": 41,
    "riskSegment": "Cannot Pay",
    "selfCureProbability": 11,
    "rollForwardRisk": 68,
    "ptpSuccessProbability": 24,
    "nbaRecommendation": "Field Visit",
    "confidenceLevel": 82,
    "scoringDate": "2026-07-20"
  },
  "paymentHistory": [
    { "dueDate": "2026-07-05", "actualPayDate": "2026-07-05", "paymentAmount": "Rp 1.650.000", "payStatus": "ON_TIME", "delayDays": 0, "recoverySource": null }
  ],
  "restructuringStatus": {
    "restructureGroupId": "RG-CUST-00001-2026-07-15-1",
    "offerStatus": "GENERATED",
    "eligibilityTier": "MANUAL_REVIEW"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `contractNo`, `custId`, `custName`, `productType`, `cycle` | string | Header fields. `cycle` is `contract_snapshot.cycle`. |
| `closedViaRestructure` | boolean | From `contract_snapshot.closed_via_restructure` — shows a "Direstrukturisasi →" badge in the header when `true`. |
| `summary.interestRate` | number | **Already scaled to a percent number** (`13.76` means 13.76% p.a.) — unlike the restructuring domain's `recommendedNewRate`, which is a raw decimal fraction (`0.1376`). See `08-restructuring.md`. Convert `contract_snapshot.interest_rate` accordingly before sending if the DB stores it as a fraction. |
| `summary.ambc` | number | Raw `contract_snapshot.ambc` value (not pre-formatted as Rupiah — the frontend renders it as a plain locale-formatted number). |
| `summary.*` (rest) | string/number | Direct 1:1 mapping to the matching `contract_snapshot` columns; money fields (`loanAmount`, `installmentAmount`, `lateFeeAmount`) are **pre-formatted** Rupiah strings. |
| `outstandingBreakdown.*` | string | Pre-formatted; `principalOutstanding` = `prnc_ots`, `interestOutstanding` = `intr_ots`, `totalOutstanding` = their sum. |
| `aiScoring.*` | — | From `ai_intelligence_output` for this exact `contract_no` — no aggregation needed. `recoveryScore`/`selfCureProbability`/`rollForwardRisk`/`ptpSuccessProbability`/`confidenceLevel` are 0-100 scaled numbers (same scale note as `02-customer.md` — the DB columns are `NUMERIC(5,4)` 0-1 decimals, multiply by 100). `riskSegment` displayed as-is. `scoringDate` is `ai_intelligence_output.scoring_date`. |
| `paymentHistory` | array | From `payment_history` filtered by `contract_no`, in display order (the frontend does not sort). `actualPayDate`/`delayDays`/`recoverySource` are `null` for unpaid installments (`payStatus: "UNPAID"`). `paymentAmount` is pre-formatted; `Rp 0` for unpaid rows. |
| `restructuringStatus` | object \| `null` | `null` when this contract has never been part of a restructuring group. Otherwise mirrors the current `restructuring_group_map` → `restructuring_recommendation_output` join for this `contract_no`: `restructureGroupId`, `offerStatus`, `eligibilityTier`. **Read-only on this page** — see Notes. |

**Field naming / casing:** same `snakeToCamelDeep` mapper convention as Customer Detail (see `02-customer.md`) — `src/domains/contract/contract.api.ts` applies it before Zod validation, so the backend can send snake_case keys directly.

**Error responses**

| Status | When | Frontend behavior |
|---|---|---|
| `404` | Unknown `contractNo` | Generic error today. |
| `401` | Expired/missing token | Logs the user out. |

---

## `GET /contracts/:contractNo/activity-log`

Collection activity timeline for one contract — **one endpoint, two consumers**: Contract Detail's own "Collection Activity Timeline" section (always fetched), and Customer Detail's per-contract expand (lazy-fetched on first expand). Both hit this exact same endpoint/hook (`useContractActivityLogQuery`) so the data is always consistent between the two pages.

**Auth required:** Yes.

**Success response — `200`** — same shape as the old (now-retired) customer-level timeline entry:

```json
[
  {
    "id": "CTR-00001-1-log-broken",
    "icon": "event_busy",
    "title": "Broken Promise (PTP)",
    "timestamp": "12 Jul 2026, 11:59 PM",
    "description": "Janji bayar tidak terdeteksi di sistem pada tanggal jatuh tempo yang dijanjikan.",
    "tone": "danger"
  },
  {
    "id": "CTR-00001-1-log-1",
    "icon": "chat",
    "title": "Automated WA Sent",
    "timestamp": "20 Jul 2026, 09:15 AM",
    "description": "Pengingat jatuh tempo tagihan kontrak CTR-00001-1 dikirim ke nasabah.",
    "tone": "default",
    "meta": { "label": "Status", "value": "Delivered", "tone": "success" }
  }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Unique per entry, React list key. |
| `icon` | string | yes | Material Symbols icon name. |
| `title` | string | yes | Bold headline, e.g. `"Broken Promise (PTP)"`, `"Outbound Call Attempt"`. |
| `timestamp` | string | yes | Pre-formatted display string, not parsed by the frontend. |
| `description` | string | yes | Free text, rendered as-is. |
| `tone` | `"default" \| "danger"` | yes | `"danger"` renders red (broken promises/failures). |
| `meta` | object | no | Optional highlighted callout: `{ label, value, tone: "success" \| "danger" }`. |

**Source tables:** `lkp_interaction` (WA/calls/contact attempts, broken PTP) and (for the "Account Assigned to Internal Team" style entries) whatever internal-assignment log the backend maintains, if any.

---

## Notes

- **Why no accept/reject buttons here:** `restructuring_group_map` can cover >1 contract at once (`CONSOLIDATE` offers). Customer-facing accept/reject lives **only** on Customer Detail (see `08-restructuring.md`) so a multi-contract group is responded to exactly once, not once per contract. This page's "Status Restrukturisasi" card is read-only by design, with a note linking to the customer page.
- **Payment history pagination:** per the design doc's own open question, payment history is returned **inline** in the same `GET /contracts/:contractNo` payload rather than as a separate paginated endpoint, since a single contract's payment history is expected to stay small. Revisit if that assumption breaks (e.g. very long-tenor contracts).
