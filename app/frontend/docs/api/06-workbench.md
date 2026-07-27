# Collector Workbench API

## Overview

The individual collector's working queue: a filterable/searchable account list on the left, and a detail panel (profile, AI reasoning, recent activity, quick actions) for whichever account is selected on the right.

**Backend status:** no backing table exists, and this is the **riskiest contract of all six modules** — it appears to synthesize customer behavioral standing + AI scoring output + customer master data + free-text search + filter-chip semantics into one paginated/filterable list, none of which exists as a ready view today. Recommended as the **last module to build**, once the query/filter/pagination patterns from the other modules are already proven.

**Consumed by:** `src/pages/CollectorWorkbenchPage.tsx` via `src/hooks/useWorkbenchFilter.ts`

**Frontend files:**
- Schema: `src/domains/workbench/workbench.schema.ts`
- API calls: `src/domains/workbench/workbench.api.ts`
- Hooks: `src/domains/workbench/useWorkbenchAccountsQuery.ts`, `src/domains/workbench/useWorkbenchActivityLogQuery.ts`
- Mock: `src/mocks/fixtures/workbench.fixtures.ts`, `src/mocks/handlers/workbench.handlers.ts`

---

## `GET /workbench/accounts`

Returns the filtered/searched account queue for the currently logged-in collector.

**Auth required:** Yes. **Note:** the account list is presumably scoped to *the requesting collector's own* assigned accounts — there is no `collectorId` param sent by the frontend today, since it's expected to be derived from the auth token server-side. Confirm this assumption before building, since if a manager/admin needs to view another collector's queue, an explicit param will need to be added.

**Query params**

| Param | Type | Required | Values | Notes |
|---|---|---|---|---|
| `filter` | string | yes | `"all"` \| `"dpd_30_plus"` \| `"high_amount"` | Which filter chip is active. `"dpd_30_plus"` = accounts with `dpdDays >= 30`. `"high_amount"` = accounts with `priority` of `"High"` or `"Critical"`. `"all"` = no filter. |
| `search` | string | yes (can be empty) | free text | Case-insensitive substring match against account `name`. Sent as `""` when the search box is empty. The frontend debounces this by 300ms before sending, so you won't get a request on every keystroke. |

Example: `GET /workbench/accounts?filter=dpd_30_plus&search=budi`

**Success response — `200`**

```json
{
  "accounts": [
    {
      "id": "ACC-99210",
      "accountId": "#ACC-99210",
      "name": "Adi Saputra",
      "initials": "AS",
      "dpdDays": 84,
      "amount": "Rp 12.500.000",
      "priority": "Critical",
      "location": "Kabupaten Bekasi, Jawa Barat",
      "paymentProbability": 82,
      "employmentStatus": "Karyawan Swasta",
      "lastPaymentDate": "14 Jan 2024",
      "aiReasoning": "Berdasarkan pola transaksi historis, debitur cenderung melakukan pembayaran setelah menerima pengingat via WhatsApp di pagi hari...",
      "aiRecommendations": [
        "Kirim template pesan penagihan persuasif (Restrukturisasi).",
        "Tawarkan perpanjangan tenor 3 bulan jika pembayaran DP dilakukan hari ini."
      ]
    }
  ],
  "totalCount": 124
}
```

### `accounts` — array, in the order they should display (frontend does not re-sort)

| Field | Type | Notes |
|---|---|---|
| `id` | string | Internal identifier, e.g. `"ACC-99210"` (no `#` prefix). Used as the React list key and as the "selected account" identifier. |
| `accountId` | string | **Display** identifier, with `#` prefix, e.g. `"#ACC-99210"`. Yes, this is redundant with `id` — kept as a separate field to match the design's exact display text. |
| `name` | string | Debtor name. Also what `search` matches against. |
| `initials` | string | Avatar initials. |
| `dpdDays` | number | Days past due. Also what the `dpd_30_plus` filter checks (`>= 30`). |
| `amount` | string | Pre-formatted Rupiah amount owed. |
| `priority` | `"Critical" \| "High" \| "Medium"` | Colors the priority chip. Also what the `high_amount` filter checks (`"High"` or `"Critical"`). |
| `location` | string | Free text, e.g. `"Kabupaten Bekasi, Jawa Barat"`. |
| `paymentProbability` | number | 0–100. Shown both as a "Score" badge and as a progress bar labeled "Probabilitas Pembayaran". |
| `employmentStatus` | string | Free text, e.g. `"Karyawan Swasta"` ("Private Employee"). |
| `lastPaymentDate` | string | Pre-formatted date, e.g. `"14 Jan 2024"`. |
| `aiReasoning` | string | Free-text paragraph explaining the AI's analysis of this account — can be long. |
| `aiRecommendations` | array of strings | Bullet-point action recommendations, in display order. Can be any length (1 item is fine, so is 5). |

### Top-level

| Field | Type | Notes |
|---|---|---|
| `totalCount` | number | Total accounts matching the current `filter`+`search` (i.e. `accounts.length` if you're not paginating, or the true total if you decide to paginate later — **this endpoint is not paginated today**, the frontend renders every returned account in one scrollable list). Shown in the "Semua Akun (N)" chip label — that count is **only accurate for the currently active filter**, so when `filter=all` and `search=""` this should be the full queue size; when a filter/search is active, it's fine (and expected) for the frontend to just show the filtered count. |

**Notes**
- There is currently **no pagination** on this endpoint — if a collector's queue can be in the hundreds, consider whether that's a problem worth solving now vs. later.
- The account currently selected in the right-hand detail panel is **not a separate `GET /workbench/accounts/:id` call** — the frontend just reads the full account object out of whichever page of `accounts` is already loaded. If you'd rather not send the full `aiReasoning`/`aiRecommendations` payload for every row in a large list, that's a reasonable optimization to propose (e.g. a lighter list-row shape + a separate detail-fetch-on-select), but it's a frontend change too, not just a backend one — coordinate before switching.

---

## `GET /workbench/activity-log`

Recent activity log shown in the account detail panel (currently global, not per-account — see note).

**Auth required:** Yes.

**Success response — `200`**

```json
[
  { "id": "wl-1", "title": "WhatsApp terkirim - Automasi System", "timestamp": "Hari ini, 09:12 WIB", "tone": "sent" },
  { "id": "wl-2", "title": "Panggilan tidak terjawab (No Response)", "timestamp": "Kemarin, 16:45 WIB", "tone": "missed" }
]
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique per entry, used as the React list key. |
| `title` | string | Free text describing the activity, e.g. `"WhatsApp terkirim - Automasi System"` ("WhatsApp sent - Automated System"). |
| `timestamp` | string | Pre-formatted, e.g. `"Hari ini, 09:12 WIB"` ("Today, 09:12 WIB"). Not parsed by the frontend. |
| `tone` | `"sent" \| "missed"` | Only two values — `"sent"` renders as a plain dot, `"missed"` renders muted. |

**This is very likely a gap worth flagging explicitly:** this endpoint takes **no account ID param today** — it returns one global activity feed regardless of which account is selected in the UI. Given the panel is titled "Log Operasional Terakhir" (recent operational log) right under a specific debtor's profile, this almost certainly *should* be scoped per-account (i.e. `GET /workbench/accounts/:accountId/activity-log`). This was carried over as-is from the original static mock and was not something the frontend migration work fixed — raise it with whoever owns this screen's requirements before building the real endpoint.

**Also not wired to anything:** the "Kirim WA" (Send WhatsApp) and "Hubungi Deskcoll" (Contact Deskcoll) quick-action buttons at the bottom of the detail panel are UI-only today — no endpoint call happens on click. These will need their own action endpoints (e.g. `POST /workbench/accounts/:accountId/actions/send-whatsapp`) once defined.
