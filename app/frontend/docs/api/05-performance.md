# Performance API

## Overview

Collector/agent leaderboard: filter bar, 3 summary tiles, a paginated ranking table, and an operational log.

**Backend status:** no backing table exists. There is currently no Collector/Agent entity anywhere in the schema (`lkp_interaction` has a bare `collector_id` varchar column, but no roster/target/achievement table). This module needs new schema design from scratch — a collectors table with targets and a way to compute achievement/collection-rate per period.

**Consumed by:** `src/pages/PerformancePage.tsx`

**Frontend files:**
- Schema: `src/domains/performance/performance.schema.ts`
- API calls: `src/domains/performance/performance.api.ts`
- Hooks: `src/domains/performance/usePerformanceFiltersQuery.ts`, `usePerformanceSummaryQuery.ts`, `useCollectorRankingQuery.ts`, `usePerformanceOperationalLogQuery.ts`
- Mock: `src/mocks/fixtures/performance.fixtures.ts`, `src/mocks/handlers/performance.handlers.ts`

This module is split into **4 separate endpoints** (unlike Dashboard's single composite endpoint) because the ranking table is paginated independently of the rest of the page.

---

## `GET /performance/filters`

Returns the options for the Branch / Area / Product filter dropdowns and the current date-range label.

**Auth required:** Yes.

**Success response — `200`**

```json
{
  "branches": ["All Branches", "Jakarta Pusat", "Jakarta Selatan", "Surabaya"],
  "areas": ["Greater Indonesia", "Java", "Sumatra"],
  "products": ["Personal Loan", "Credit Card", "Auto Loan"],
  "dateRange": "Oct 01 - Oct 31, 2023"
}
```

| Field | Type | Notes |
|---|---|---|
| `branches` / `areas` / `products` | array of strings | Dropdown option lists, in display order. First item is treated as the "no filter" default (e.g. `"All Branches"`). |
| `dateRange` | string | Pre-formatted display label for the current reporting period, e.g. `"Oct 01 - Oct 31, 2023"`. |

**Important — not implemented yet:** the dropdowns render these options but **selecting a filter does not currently trigger a refetch of anything** — there's no `branch`/`area`/`product`/`dateRange` param wired into the other 3 endpoints below. If/when filtering needs to actually work, `usePerformanceSummaryQuery`, `useCollectorRankingQuery`, and `usePerformanceOperationalLogQuery` will need to accept and forward these filter values as query params — flag this explicitly to whoever picks up that work, since it's a real gap, not a documentation omission.

---

## `GET /performance/summary`

The 3 tiles at the top of the page: total achievement, active collectors, average productivity.

**Auth required:** Yes.

**Success response — `200`**

```json
{
  "totalAchievement": "Rp 4.280.000.000",
  "achievementChange": "+12.4% from last month",
  "activeCollectors": 142,
  "activeCollectorsProgress": 82,
  "avgProductivityIndex": 8.4
}
```

| Field | Type | Notes |
|---|---|---|
| `totalAchievement` | string | Pre-formatted Rupiah amount. |
| `achievementChange` | string | Pre-formatted trend sentence, e.g. `"+12.4% from last month"`. |
| `activeCollectors` | number | Raw count, e.g. `142`. |
| `activeCollectorsProgress` | number | 0–100, drives a small progress bar under the active-collectors tile (presumably "collectors active today ÷ total roster" — confirm the intended meaning with whoever owns this metric). |
| `avgProductivityIndex` | number | Free-scale index shown as-is, e.g. `8.4`. |

---

## `GET /performance/collectors`

Paginated collector leaderboard.

**Auth required:** Yes.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `page` | number | yes | 1-indexed. Sent as `?page=1`, `?page=2`, etc. |

**Success response — `200`**

```json
{
  "collectors": [
    { "rank": 1, "name": "Aditya Nugroho", "initials": "AN", "employeeId": "#99281", "target": "500,000,000", "achievement": "485,250,000", "collectionRate": 97.05, "productivityIndex": 9.8, "ratingTone": "good" }
  ],
  "pageInfo": { "showingFrom": 1, "showingTo": 5, "totalCollectors": 142, "totalPages": 3 }
}
```

### `collectors` — array, one row per collector on this page

| Field | Type | Notes |
|---|---|---|
| `rank` | number | Overall leaderboard rank (not per-page rank — e.g. page 2's first row should be rank 6 if page size is 5, not rank 1). |
| `name` | string | Collector's full name. |
| `initials` | string | Avatar initials. |
| `employeeId` | string | Display format includes the `#`, e.g. `"#99281"`. |
| `target` | string | Pre-formatted number **without currency prefix or the leading "Rp"**, e.g. `"500,000,000"` — note this differs from other modules' Rupiah fields (those include `"Rp "`); the UI prepends "Rp" itself in the table header here instead. Match this exact formatting (thousands separator, no prefix) to avoid a double "Rp Rp" or missing prefix. |
| `achievement` | string | Same format as `target`. |
| `collectionRate` | number | Percentage as a plain number, e.g. `97.05` (not `"97.05%"` — this one *is* a real number, unlike most percentage fields elsewhere in this API which are pre-formatted strings). The frontend appends `%` and renders a progress bar from it. |
| `productivityIndex` | number | Free-scale index, e.g. `9.8`. |
| `ratingTone` | `"good" \| "fair" \| "poor"` | Colors the collection-rate progress bar (green/blue/red). Pick thresholds server-side (e.g. `good` ≥ 85%, `fair` ≥ 60%, else `poor`) and keep them consistent — the frontend does not compute this itself, it trusts whatever tone you send. |

### `pageInfo`

| Field | Type | Notes |
|---|---|---|
| `showingFrom` / `showingTo` | number | 1-indexed range describing this page, e.g. `{ showingFrom: 6, showingTo: 10 }` for page 2 at page size 5. Powers the "Showing X to Y of Z collectors" text. |
| `totalCollectors` | number | Grand total across all pages. |
| `totalPages` | number | Used to render page number buttons and to disable "next" on the last page. |

**Notes**
- Page size is implicitly 5 in the current mock (`ALL_COLLECTORS.length` in `performance.fixtures.ts`) but **the frontend does not assume any fixed page size** — it only trusts `pageInfo`. Pick whatever page size makes sense server-side.
- "Export CSV" and "Bulk Action" buttons exist in the UI but are **not wired to any endpoint yet**.

---

## `GET /performance/operational-log`

**Auth required:** Yes.

**Success response — `200`**

```json
[
  { "id": "log-1", "message": "Sistem memperbarui target bulanan untuk cabang Jakarta Pusat.", "timestamp": "Hari ini, 09:12 AM", "tone": "neutral" },
  { "id": "log-2", "message": "Aditya Nugroho mencapai 110% dari target harian produk Personal Loan.", "timestamp": "Hari ini, 08:45 AM", "tone": "success" }
]
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique per entry, used as the React list key. |
| `message` | string | Free text, currently written in Bahasa Indonesia in the mock — keep whatever language your ops team uses. |
| `timestamp` | string | Pre-formatted relative/display time, e.g. `"Hari ini, 09:12 AM"` (Indonesian for "Today, 09:12 AM") or `"Kemarin, 11:30 PM"` ("Yesterday, ..."). Not parsed by the frontend. |
| `tone` | `"neutral" \| "success" \| "muted"` | Colors the leading dot marker. |
