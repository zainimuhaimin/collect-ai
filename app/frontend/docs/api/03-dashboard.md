# Dashboard API

## Overview

The consolidated portfolio dashboard: 4 KPI tiles, a DPD-bucket-vs-PTP-status chart, a contactability funnel, and a table of high-priority broken-PTP accounts.

**Backend status:** no dedicated dashboard table exists, but every field here is a portfolio-level rollup over the same tables Customer Detail uses (`ai_intelligence_output`, `customer_behavioral_standing`, plus `lkp_interaction` for the contact funnel). Recommended as the **second real endpoint to build**, after Customer Detail, since the aggregation logic can reuse whatever Customer Detail's backend work establishes.

Everything below is returned by **one single endpoint** — the frontend fetches the whole dashboard in one round trip rather than one request per widget.

**Consumed by:** `src/pages/DashboardPage.tsx`

**Frontend files:**
- Schema: `src/domains/dashboard/dashboard.schema.ts`
- API calls: `src/domains/dashboard/dashboard.api.ts`
- Hook: `src/domains/dashboard/useDashboardSummaryQuery.ts`
- Mock: `src/mocks/fixtures/dashboard.fixtures.ts`, `src/mocks/handlers/dashboard.handlers.ts`

---

## `GET /dashboard/summary`

**Auth required:** Yes.

**Request:** no body, no query params (no date-range/branch filter yet — see notes).

**Success response — `200`**

```json
{
  "kpis": [
    { "icon": "account_balance_wallet", "label": "Total Outstanding", "value": "Rp 4.280.000.000", "change": "+4.2%", "trend": "up", "tone": "positive" },
    { "icon": "person_off", "label": "Active Delinquent Accounts", "value": "12,482", "change": "-1.5%", "trend": "down", "tone": "negative" }
  ],
  "dpdBuckets": [
    { "label": "C0 (1-30)", "settled": 70, "activePtp": 20, "broken": 10 },
    { "label": "C1 (31-60)", "settled": 55, "activePtp": 15, "broken": 20 }
  ],
  "contactabilityFunnel": [
    { "label": "Attempts (100k)", "value": "100k", "percentage": "100%" },
    { "label": "Contacted (65k)", "value": "65k", "percentage": "65%" }
  ],
  "channelEfficiency": { "channel": "WhatsApp", "rate": "82%" },
  "brokenPtpPriorities": [
    {
      "customerId": "#CA-88901",
      "name": "Andi Saputra",
      "initials": "AS",
      "amount": "Rp 12.500.000",
      "ambcValue": "0.94",
      "ambcTier": "High",
      "lastAction": "Broken Promise",
      "lastActionDate": "Oct 24, 2023"
    }
  ],
  "syncNote": "Data last synchronized: 2 minutes ago"
}
```

### `kpis` — array of exactly 4 stat tiles (order is display order, left to right)

| Field | Type | Notes |
|---|---|---|
| `icon` | string | Material Symbols icon name. |
| `label` | string | Tile caption, e.g. `"Total Outstanding"`. |
| `value` | string | **Pre-formatted** headline number, e.g. `"Rp 4.280.000.000"` or `"12,482"` — send it exactly as it should display. |
| `change` | string | Pre-formatted delta, e.g. `"+4.2%"` or `"Stable"`. |
| `trend` | `"up" \| "down" \| "flat"` | Picks the trend arrow icon. |
| `tone` | `"neutral" \| "positive" \| "negative"` | Picks the delta's text color — set this independently of `trend` (e.g. a *decreasing* delinquent-accounts count is `trend: "down"` but `tone: "positive"`, since fewer delinquents is good). |

### `dpdBuckets` — array (one bar per DPD aging bucket)

| Field | Type | Notes |
|---|---|---|
| `label` | string | Bucket name, e.g. `"C0 (1-30)"` (days-past-due range). |
| `settled` / `activePtp` / `broken` | number | Raw counts (or any consistent unit) — the frontend computes each segment's share of the bar as `value / (settled + activePtp + broken)`, so these three don't need to sum to 100 or to any fixed total. |

### `contactabilityFunnel` — array (funnel stages, in the order they should render top-to-bottom)

| Field | Type | Notes |
|---|---|---|
| `label` | string | e.g. `"Attempts (100k)"` — note the count is baked into the label string itself, not a separate field. |
| `value` | string | Short value shown elsewhere if needed, e.g. `"100k"`. |
| `percentage` | string | Pre-formatted percentage of the funnel's first stage, e.g. `"65%"`. |

### `channelEfficiency`

| Field | Type | Notes |
|---|---|---|
| `channel` | string | Name of the best-performing contact channel, e.g. `"WhatsApp"`. |
| `rate` | string | Pre-formatted efficiency rate, e.g. `"82%"`. |

### `brokenPtpPriorities` — array (table rows, priority order)

| Field | Type | Notes |
|---|---|---|
| `customerId` | string | Display ID shown in the table, e.g. `"#CA-88901"`. **Note:** this is a *different ID format* than Customer Detail's `customerId` path param (`C-90218341`) — the frontend currently does a naive `#CA- → C-` string replace to link a dashboard row to `/customers/:id`, which is fragile. Recommend aligning on one ID format between this module and Customer Detail so that hack can be removed. |
| `name` | string | Debtor name. |
| `initials` | string | Avatar initials. |
| `amount` | string | Pre-formatted Rupiah amount. |
| `ambcValue` | string | AMBC (AI-based prioritization) score, pre-formatted as a decimal string e.g. `"0.94"`. |
| `ambcTier` | `"High" \| "Medium" \| "Low"` | Drives the colored chip. |
| `lastAction` | string | e.g. `"Broken Promise"`, `"WA Unread > 48h"`. |
| `lastActionDate` | string | Pre-formatted date, e.g. `"Oct 24, 2023"`. |

### `syncNote`

| Field | Type | Notes |
|---|---|---|
| `syncNote` | string | Freeform footer text, e.g. `"Data last synchronized: 2 minutes ago"`. Compute this server-side (e.g. from the scoring pipeline's last run timestamp) rather than hardcoding. |

**Notes**
- There is no server-side pagination or filtering on this endpoint today — the whole payload is fetched at once on every dashboard visit. If `brokenPtpPriorities` can grow large in production, consider adding a `limit`/`cursor` param before that becomes a problem (React Query will cache the response for 30s regardless, so this isn't urgent).
- "Export Report" and "Share Insight" buttons in the UI are **not wired to any endpoint yet** — decide with product what those should do (download a file? open a share dialog?) before building them.
