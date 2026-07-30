# Customer API

## Overview

Covers three things: the paginated/filterable customer list, the 360° Customer Detail view (balance, CBS behavioral standing, AI risk/recovery scoring, restructuring options), and the lightweight list of a customer's contracts used by Customer Detail's expandable "Kontrak Milik Customer Ini" section.

**Backend status:** maps directly onto tables that already exist in `app/machine-learning/config/schema_combined.sql`:
- `ai_intelligence_output` → `riskSegment`, `recoveryScore`, `selfCureProbability`, `rollForwardRisk`, `ptpSuccessProbability`, `nbaRecommendation` (joined by `cust_id`, taking the customer's primary/highest-DPD contract — see the note under Customer Detail below).
- `customer_behavioral_standing` (CBS) → `behavioralGrade`, `bListStatus`, `restructureCount`, `activeContractCount`.
- `contract_snapshot` → `dpdDays`/`outstanding` roll-ups for the list, and the per-contract fields in `GET /customers/:custId/contracts`.
- `lkp_interaction` → the `broken_ptp` filter (latest `ptp_status = 'BROKEN'` per contract).

This corrects the old `customerDetailSchema`, which had an invented `riskTier: "HIGH RISK" | "MEDIUM RISK" | "LOW RISK"` enum with no real backend source. The real `risk_segment` column's values (`Cannot Pay` / `Self Cure` / `Won't Pay`) are used as-is everywhere now — see `src/domains/shared/riskSegment.ts`.

**Consumed by:** `src/pages/CustomerListPage.tsx`, `src/pages/CustomerDetailPage.tsx`

**Frontend files:**
- Schema: `src/domains/customer/customer.schema.ts`
- API calls: `src/domains/customer/customer.api.ts`
- Hooks: `src/domains/customer/useCustomerDetailQuery.ts`, `src/domains/customer/useCustomerListQuery.ts`, `src/domains/customer/useCustomerContractsQuery.ts`
- Mock: `src/mocks/fixtures/customer.fixtures.ts`, `src/mocks/handlers/customer.handlers.ts`

Customer Detail also renders the "Opsi Restrukturisasi" card and the per-contract activity log — see [`08-restructuring.md`](./08-restructuring.md) and [`07-contract.md`](./07-contract.md) respectively; those are separate endpoints/domains consumed by the same page.

---

## `GET /customers`

Paginated, filterable, searchable customer list.

**Auth required:** Yes.

**Query params**

| Param | Type | Notes |
|---|---|---|
| `filter` | `all` \| `dpd_30_plus` \| `high_amount` \| `broken_ptp` \| `high_ambc` | See table below. |
| `search` | string | Case-insensitive substring match against customer name or `custId`. Empty string = no search filtering. |
| `page` | number | 1-indexed. |
| `pageSize` | number | Rows per page (the frontend currently always sends `10`). |

**Filter semantics** — note `broken_ptp`/`high_ambc` are really per-*contract* attributes; at the customer level they mean "this customer has ≥1 contract matching":

| Filter | Condition |
|---|---|
| `all` | No filter. |
| `dpd_30_plus` | `dpdDays >= 30` (customer's max DPD across contracts). |
| `high_amount` | `priority` is `High` or `Critical`. |
| `broken_ptp` | Customer has ≥1 contract whose latest `lkp_interaction.ptp_status = 'BROKEN'`. |
| `high_ambc` | Customer has ≥1 contract whose `contract_snapshot.ambc` is above the "high" threshold (mock uses `>= 10,000,000`; backend should confirm the real threshold, ideally shared with `07-contract.md`'s `high_ambc` filter). |

**Success response — `200`**

```json
{
  "customers": [
    { "custId": "CUST-00001", "name": "Budi Pratama Sitorus", "dpdDays": 62, "amount": "Rp 18.190.000", "priority": "Critical" }
  ],
  "pageInfo": { "showingFrom": 1, "showingTo": 10, "totalCustomers": 18, "totalPages": 2 }
}
```

| Field | Type | Notes |
|---|---|---|
| `customers[].custId` | string | Primary identifier, used to build `/customers/:custId` links. |
| `customers[].name` | string | Full name. |
| `customers[].dpdDays` | number | Max DPD across the customer's active contracts. |
| `customers[].amount` | string | **Pre-formatted** total outstanding across all contracts, e.g. `"Rp 18.190.000"`. |
| `customers[].priority` | `"Medium" \| "High" \| "Critical"` | Drives the priority chip. Not a raw DB column today — backend should define the derivation (likely a function of DPD + outstanding amount + risk_segment) when implementing for real. |
| `pageInfo.showingFrom` / `.showingTo` | number | 1-indexed inclusive row range for the current page (`0`/`0` when the result set is empty). |
| `pageInfo.totalCustomers` | number | Total rows matching `filter`+`search`, before pagination. |
| `pageInfo.totalPages` | number | `ceil(totalCustomers / pageSize)`, minimum `1`. |

---

## `GET /customers/:custId`

Returns the 360° profile: balance, risk/recovery AI scoring, and CBS behavioral standing.

**Auth required:** Yes.

**Success response — `200`**

```json
{
  "custId": "CUST-00001",
  "name": "Budi Pratama Sitorus",
  "initials": "BP",
  "outstandingBalance": "Rp 18.190.000",
  "riskSegment": "Cannot Pay",
  "riskScore": 59,
  "recoveryScore": 41,
  "selfCureProbability": 11,
  "rollForwardRisk": 68,
  "ptpSuccessProbability": 24,
  "nbaRecommendation": "Field Visit",
  "behavioralGrade": "D",
  "bListStatus": "Y",
  "restructureCount": 0,
  "activeContractCount": 2
}
```

| Field | Type | Notes |
|---|---|---|
| `custId` | string | Echo of the requested path param. |
| `name` | string | Full name. |
| `initials` | string | For the avatar circle. |
| `outstandingBalance` | string | **Pre-formatted** total across all active contracts. |
| `riskSegment` | `"Cannot Pay" \| "Self Cure" \| "Won't Pay"` | From `ai_intelligence_output.risk_segment`, **displayed as-is** — do not translate to invented strings. See "Which contract's scoring?" below. |
| `riskScore` | number, 0-100 | Drives a progress bar. Not a literal DB column — mock derives it as `100 - recoveryScore`; backend should define a real derivation (or drop it if product decides `recoveryScore` alone is enough). |
| `recoveryScore` | number, 0-100 | From `ai_intelligence_output.recovery_score`. **Scale note:** the DB column is `NUMERIC(5,4)` (0-1 decimal). The frontend expects an already-0-100-scaled number — multiply by 100 before sending. |
| `selfCureProbability` | number, 0-100 | Same scale note as `recoveryScore`. From `ai_intelligence_output.self_cure_probability`. |
| `rollForwardRisk` | number, 0-100 | Same scale note. From `ai_intelligence_output.roll_forward_risk`. |
| `ptpSuccessProbability` | number, 0-100 | Same scale note. From `ai_intelligence_output.ptp_success_probability`. |
| `nbaRecommendation` | string | From `ai_intelligence_output.nba_recommendation`. |
| `behavioralGrade` | string (single char) | From `customer_behavioral_standing.behavioral_grade`. |
| `bListStatus` | `"Y" \| "N"` | From `customer_behavioral_standing.b_list_status`. |
| `restructureCount` | number | From `customer_behavioral_standing.restructure_count`. |
| `activeContractCount` | number | From `customer_behavioral_standing.active_contract_count`. |

**Which contract's scoring?** `ai_intelligence_output` is keyed by `contract_no`, not `cust_id` — a customer can have several contracts, each independently scored. This mock takes the customer's **highest-DPD contract** as the "primary" one for `riskSegment`/`recoveryScore`/etc. The real backend needs a data-team decision here: highest DPD, highest outstanding, or a proper customer-level aggregate score. Flag this before implementing.

**Field naming / casing:** the frontend's Zod schema is camelCase by convention; the real backend's tables are snake_case. `src/domains/customer/customer.api.ts` runs the raw response through `snakeToCamelDeep` (`src/api/caseTransform.ts`) before validating against the schema, so the backend is free to send snake_case keys (`recovery_score`, `risk_segment`, ...) — no frontend schema changes needed either way.

**Error responses**

| Status | When | Frontend behavior |
|---|---|---|
| `404` | Unknown `custId` | Generic error today — a dedicated "customer not found" state would be a good follow-up. |
| `401` | Expired/missing token | Logs the user out. |

---

## `GET /customers/:custId/contracts`

Lightweight list of a customer's contracts, powering the expandable "Kontrak Milik Customer Ini" section on Customer Detail.

**Auth required:** Yes.

**Success response — `200`**

```json
[
  { "contractNo": "CTR-00001-1", "productType": "Personal Loan", "dpdCurrent": 62, "outstanding": "Rp 12.450.000", "riskSegment": "Cannot Pay" },
  { "contractNo": "CTR-00001-2", "productType": "Multiguna", "dpdCurrent": 12, "outstanding": "Rp 5.740.000", "riskSegment": "Self Cure" }
]
```

| Field | Type | Notes |
|---|---|---|
| `contractNo` | string | Links to `/contracts/:contractNo` (full detail — see `07-contract.md`) and is the key used to lazy-fetch that contract's activity log on first expand. |
| `productType` | string | e.g. `"Personal Loan"`, `"KPR"`, `"Multiguna"`, `"Kartu Kredit"`. |
| `dpdCurrent` | number | From `contract_snapshot.dpd_current`. |
| `outstanding` | string | **Pre-formatted**, `prnc_ots + intr_ots`. |
| `riskSegment` | `"Cannot Pay" \| "Self Cure" \| "Won't Pay"` | This specific contract's segment (not the customer-level rollup above) — displayed as-is in a chip. |

**Notes**
- On first expand of a row, the frontend separately calls `GET /contracts/:contractNo/activity-log` (documented in `07-contract.md`) — that response is cached per `contractNo` and shared with Contract Detail's own timeline section.
