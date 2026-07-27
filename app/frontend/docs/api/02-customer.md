# Customer Detail API

## Overview

Powers the 360° debtor view: balance, PTP (Promise-to-Pay) history, AI risk/recovery scoring, and a collection activity timeline.

**Backend status:** of all six modules, this one maps most directly onto tables that already exist in `app/machine-learning/config/schema_combined.sql`:
- `ai_intelligence_output` → `recoveryScore`, `selfCureProbability`, `ptpSuccessProbability`, risk fields (joined by `cust_id`/`contract_no`).
- `customer_behavioral_standing` (CBS) → `behavioral_grade`/`recovery_effort_level`/`ptp_reliability_index` roughly map to `recoveryLabel`/`riskTier`/`riskTierLevel` (exact field mapping needs a data-team conversation, but the entities line up).
- The collection activity timeline (SMS sent, calls, broken promises) would come from `lkp_interaction` and payment records, not from the scoring tables.

This makes Customer Detail the recommended **first real endpoint to build** once backend work starts.

**Consumed by:** `src/pages/CustomerDetailPage.tsx`

**Frontend files:**
- Schema: `src/domains/customer/customer.schema.ts`
- API calls: `src/domains/customer/customer.api.ts`
- Hooks: `src/domains/customer/useCustomerDetailQuery.ts`, `src/domains/customer/useCustomerTimelineQuery.ts`
- Mock: `src/mocks/fixtures/customer.fixtures.ts`, `src/mocks/handlers/customer.handlers.ts`

---

## `GET /customer/:customerId`

Returns the full profile card + summary metrics + AI scoring for one customer.

**Auth required:** Yes.

**Path params**

| Param | Type | Notes |
|---|---|---|
| `customerId` | string | Comes straight from the URL, e.g. `/customers/C-90218341` in the app → `customerId = "C-90218341"`. This is presumably `cust_id` in the DB, but confirm the exact ID format/prefix convention with the data team. |

**Success response — `200`**

```json
{
  "id": "C-90218341",
  "name": "Budi Pratama Sitorus",
  "initials": "BP",
  "verified": true,
  "outstandingBalance": "Rp 12.450.000",
  "balanceChange": "-12% since last month",
  "ptpHistory": { "success": 4, "broken": 2, "rate": "66%" },
  "ptpMonths": [
    { "month": "May", "result": "success" },
    { "month": "Jun", "result": "success" },
    { "month": "Jul", "result": "broken" },
    { "month": "Aug", "result": "success" },
    { "month": "Sep", "result": "success" },
    { "month": "Oct", "result": "broken" }
  ],
  "riskTier": "HIGH RISK",
  "riskTierLevel": "Tier 3",
  "riskScore": 82,
  "recoveryScore": 74,
  "recoveryLabel": "Moderate Recovery",
  "selfCureProbability": "12.5%",
  "ptpSuccessProbability": "68.2%",
  "targetNbaAction": "Personalized SMS Hook",
  "aiJustification": "Nasabah menunjukkan pola pembayaran yang reaktif terhadap pengingat digital pada akhir pekan..."
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Echo of the requested `customerId`. |
| `name` | string | Full name. |
| `initials` | string | For the avatar circle. |
| `verified` | boolean | Shows a "Verified Account" badge when `true`. |
| `outstandingBalance` | string | **Pre-formatted** as Indonesian Rupiah, e.g. `"Rp 12.450.000"` — the frontend does not format numbers, it displays this string verbatim. |
| `balanceChange` | string | Pre-formatted trend label, e.g. `"-12% since last month"`. |
| `ptpHistory.success` | number | Count of kept promises-to-pay (last 12 months). |
| `ptpHistory.broken` | number | Count of broken promises. |
| `ptpHistory.rate` | string | Pre-formatted success rate, e.g. `"66%"`. |
| `ptpMonths` | array of 6–12 items | Powers the small bar sparkline. Each item: `{ month: string, result: "success" \| "broken" }`. Send however many months you have; the UI just renders one bar per entry. |
| `riskTier` | `"HIGH RISK" \| "MEDIUM RISK" \| "LOW RISK"` | **Exact string values matter** — the frontend switches styling on these literals. |
| `riskTierLevel` | string | Free-text sub-label next to the tier, e.g. `"Tier 3"`. |
| `riskScore` | number | 0–100, drives a progress bar. |
| `recoveryScore` | number | 0–100 (shown in a circular badge). |
| `recoveryLabel` | string | Free-text label next to the score, e.g. `"Moderate Recovery"`. |
| `selfCureProbability` | string | **Pre-formatted percentage string**, e.g. `"12.5%"` — not a raw number. The frontend parses the leading number out of this string for a progress bar, so keep the `"<number>%"` shape. |
| `ptpSuccessProbability` | string | Same format as above. |
| `targetNbaAction` | string | The AI's recommended "Next Best Action", shown as a button label, e.g. `"Personalized SMS Hook"`. |
| `aiJustification` | string | Free-text paragraph explaining the AI's reasoning — rendered in a highlighted banner. Can be long; no length limit enforced client-side. |

**Error responses**

| Status | When | Frontend behavior |
|---|---|---|
| `404` | Unknown `customerId` | Currently surfaces as a generic error (see root README conventions) — a dedicated "customer not found" UI state would be a good follow-up once this is a real endpoint. |
| `401` | Expired/missing token | Logs the user out. |

---

## `GET /customer/:customerId/timeline`

Returns the collection activity timeline (chronological log of contact attempts, promises, and system actions) for one customer.

**Auth required:** Yes.

**Path params:** same `customerId` as above.

**Success response — `200`**

An array, newest-first (the frontend does not sort it — send it in display order):

```json
[
  {
    "id": "tl-1",
    "icon": "sms",
    "title": "Automated SMS Sent",
    "timestamp": "12 Oct 2023, 10:45 AM",
    "description": "\"Halo Budi, mohon segera melakukan pelunasan tagihan Anda...\"",
    "tone": "default",
    "meta": { "label": "Status", "value": "Delivered", "tone": "success" }
  },
  {
    "id": "tl-3",
    "icon": "event_busy",
    "title": "Broken Promise (PTP)",
    "timestamp": "05 Oct 2023, 11:59 PM",
    "description": "Janji bayar sebesar Rp 1.500.000 tidak terdeteksi di sistem pada tanggal jatuh tempo yang dijanjikan.",
    "tone": "danger"
  }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Unique per entry, used as the React list key. |
| `icon` | string | yes | A [Material Symbols](https://fonts.google.com/icons) icon name (e.g. `sms`, `call`, `event_busy`, `person_add`). Pick whatever best represents the event type — the frontend just passes this string straight to the icon font. |
| `title` | string | yes | Bold headline for the entry, e.g. `"Inbound Call Received"`. |
| `timestamp` | string | yes | **Pre-formatted display string**, not an ISO date — e.g. `"10 Oct 2023, 02:15 PM"`. The frontend does not parse or reformat it. |
| `description` | string | yes | Body text. Can contain quoted message text, agent names, etc. — free text, rendered as-is. Often written in Bahasa Indonesia in the current mock; keep the language your ops team actually uses here. |
| `tone` | `"default" \| "danger"` | yes | `"danger"` renders the entry in red (used for broken promises / failures). |
| `meta` | object | no | Optional small highlighted callout at the end of the description, e.g. a delivery status. Shape: `{ label: string, value: string, tone: "success" \| "danger" }`. Omit the whole field if there's nothing to highlight. |

**Notes**
- There's a "Load Full History" button in the UI that is currently **not wired to anything** (no pagination/params implemented yet). If your timeline can be long, decide on a pagination or `?before=<timestamp>` cursor param before that button gets wired up — flag this to whoever picks up that work.
