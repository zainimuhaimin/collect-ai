# CollectAI Frontend — API Reference

This folder documents every HTTP endpoint the CollectAI frontend (`app/frontend`) calls. It exists so a backend team can implement a real API against an already-agreed contract instead of guessing it from React code.

**Status today: the real backend now exists** — see [`app/backend/`](../../../backend/README.md). Every endpoint documented here is implemented against the shared Postgres database, and `app/frontend/.env.development` ships with `VITE_ENABLE_MSW=false`, so a local dev session talks to the real API by default.

The [MSW](https://mswjs.io/) fixtures in `src/mocks/` are still maintained and still useful — set `VITE_ENABLE_MSW=true` to run the UI with no backend or database at all (this is what Docker Compose does by default). Because mock and real go through the exact same `ky` + React Query + Zod code, the fixtures also double as a live, readable example of every response shape below.

Two things to keep in mind when reading the rest of this folder:

- **The shapes below are the contract that is already live.** If a document here disagrees with the backend, the backend's OpenAPI schema at `http://localhost:8000/docs` is the source of truth — please fix the doc.
- **Three modules described here as "new" are built:** Auth (`01-auth.md`), Restructuring Approval (`09-restructuring-approval.md`), and AI Reasoning (no numbered doc file yet — see the row below and `app/backend/README.md` §14 for the full contract with curl examples). The "Backend status" column in the table below reflects the *original* build-priority assessment and is kept for historical context, not as current status.

## Modules

Read them in this order — it roughly matches build priority (clearest backend contract first, most-invented-from-scratch last). Per `frontend-layout-upgrade-tasks.md`, Performance and Collector Workbench (formerly modules 5-6 here) were dropped entirely — no backend was ever built for either, and their UI patterns (filter chips, pagination, activity log) were folded into Customer/Contract instead.

| # | Module | File | Backend status |
|---|---|---|---|
| 1 | Auth | [`01-auth.md`](./01-auth.md) | New — needs a real identity/session system |
| 2 | Customer | [`02-customer.md`](./02-customer.md) | **Maps closely to existing tables** (`ai_intelligence_output`, `customer_behavioral_standing`) |
| 3 | Dashboard | [`03-dashboard.md`](./03-dashboard.md) | Computable as rollups over the same tables as Customer/Contract |
| 4 | AI Intelligence (governance) | [`04-ai-intelligence.md`](./04-ai-intelligence.md) | **No backing table today** — Phase 1 (Bobot CBS) only; needs a new `model_governance_config` table |
| 5 | Contract | [`07-contract.md`](./07-contract.md) | **Maps closely to existing tables** (`contract_snapshot`, `payment_history`, `ai_intelligence_output`, `lkp_interaction`) |
| 6 | Restructuring (customer-facing) | [`08-restructuring.md`](./08-restructuring.md) | **Mostly exists** — mirrors `app/backend/schemas/restructuring.py` / `restructuring_recommendation_output` |
| 7 | Restructuring Approval | [`09-restructuring-approval.md`](./09-restructuring-approval.md) | New — approve/reject queue + audit log over `restructuring_recommendation_output` |
| 8 | AI Reasoning | *(no numbered doc yet — see `src/domains/ai-reasoning/` + `app/backend/README.md` §14)* | New — hyper-personalization per debtor over `ai_reasoning_output`, calls Gemini |

## Conventions used across every module

- **Base URL**: all paths below are written relative to the API base URL, e.g. `GET /auth/me` means `{VITE_API_BASE_URL}/auth/me`. In dev, `VITE_API_BASE_URL` defaults to `/api` (see `app/frontend/.env.development`).
- **Auth**: unless a module says otherwise, every request sends `Authorization: Bearer <token>` once a user is logged in (see [`01-auth.md`](./01-auth.md)). A `401` response anywhere clears the stored token and forces the user back to `/login`.
- **Content type**: all requests/responses are JSON.
- **Validation**: every response is validated at runtime against a [Zod](https://zod.dev/) schema before the frontend ever touches it. If a real backend's response doesn't match the documented shape *exactly* (missing field, wrong type, extra required field the frontend doesn't expect isn't a problem — Zod only rejects on missing/mismatched fields, not extra ones), the frontend surfaces a generic "server returned data in an unexpected format" error instead of crashing or rendering garbage. This is why the shapes below must be followed precisely.
- **Errors**: the frontend does not parse error response *bodies* today (no documented error envelope). It only inspects the HTTP status code:
  - `401` → session expired, log the user out.
  - `408/429/500/502/503/504` on `GET` requests → retried automatically (up to 2 extra attempts) before surfacing an error.
  - Any other non-2xx → generic "Something went wrong (status N)" error shown to the user.
  - A backend is still free to return a descriptive JSON error body (e.g. `{ "message": "..." }`) for its own logs/tooling — the frontend just won't display it yet. If you want the frontend to show real backend error messages, that's a small, welcome follow-up (see the note in `01-auth.md`).
- **Where the code lives** (same layout in every module): `src/domains/<module>/<module>.schema.ts` (Zod schemas + types), `src/domains/<module>/<module>.api.ts` (the actual `fetch` calls), `src/domains/<module>/use*Query.ts` / `use*Mutation.ts` (React Query hooks consumed by pages), `src/mocks/fixtures/<module>.fixtures.ts` + `src/mocks/handlers/<module>.handlers.ts` (the current mock implementation — useful as a live example of every shape below).

## Switching between mock and the real backend

No frontend code changes either way — only configuration:

**Real backend (default in `.env.development`):**

1. `VITE_ENABLE_MSW=false`.
2. Leave `VITE_API_BASE_URL=/api`; the Vite dev proxy rewrites `/api` → `{VITE_API_PROXY_TARGET}/api/v1`, so the backend's version prefix stays out of application code. For a deployed build, point `VITE_API_BASE_URL` at the real API base URL instead.

**Mock (no backend/database needed):**

1. Set `VITE_ENABLE_MSW=true`.
2. Note `auth.handlers.ts` is deliberately excluded from the handler aggregate, and MSW runs with `onUnhandledRequest: 'bypass'` — so `/auth/*` still falls through the proxy to the real backend. Running fully offline means login will fail unless you add those handlers back.

**Historical note — the original mock-to-real checklist:**

1. Set `VITE_API_BASE_URL` to the real API's base URL (e.g. in `.env.local` or `.env.production`).
2. Set `VITE_ENABLE_MSW=false`.
3. Remove that module's handler array from `src/mocks/handlers/index.ts` once every module it covers is real (optional cleanup — leaving it costs nothing since MSW is fully disabled by the flag above, and its code is tree-shaken out of production builds entirely).

That's it — same `ky` client, same Zod validation, same React Query hooks, same pages.
