# CollectAI Frontend — API Reference

This folder documents every HTTP endpoint the CollectAI frontend (`app/frontend`) calls. It exists so a backend team can implement a real API against an already-agreed contract instead of guessing it from React code.

**Status today:** no real backend exists yet. Every endpoint below is currently served by [MSW](https://mswjs.io/) fixtures in `src/mocks/`, which the frontend hits through the exact same `ky` + React Query code that will call a real server later. Switching from mock to real is a two-variable change — see [Switching from mock to a real backend](#switching-from-mock-to-a-real-backend) below.

## Modules

Read them in this order — it roughly matches build priority (clearest backend contract first, most-invented-from-scratch last):

| # | Module | File | Backend status |
|---|---|---|---|
| 1 | Auth | [`01-auth.md`](./01-auth.md) | New — needs a real identity/session system |
| 2 | Customer Detail | [`02-customer.md`](./02-customer.md) | **Maps closely to existing tables** (`ai_intelligence_output`, `customer_behavioral_standing`) |
| 3 | Dashboard | [`03-dashboard.md`](./03-dashboard.md) | Computable as rollups over the same tables as Customer Detail |
| 4 | AI Intelligence (governance) | [`04-ai-intelligence.md`](./04-ai-intelligence.md) | **No backing table today** — despite the name, this is model-governance config, not the scoring pipeline itself |
| 5 | Performance | [`05-performance.md`](./05-performance.md) | **No backing table today** — no Collector/Agent entity exists yet |
| 6 | Collector Workbench | [`06-workbench.md`](./06-workbench.md) | **No backing table today** — riskiest/most novel contract |

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

## Switching from mock to a real backend

Once real endpoints exist for a module, no frontend code needs to change — only configuration:

1. Set `VITE_API_BASE_URL` to the real API's base URL (e.g. in `.env.local` or `.env.production`).
2. Set `VITE_ENABLE_MSW=false`.
3. Remove that module's handler array from `src/mocks/handlers/index.ts` once every module it covers is real (optional cleanup — leaving it costs nothing since MSW is fully disabled by the flag above, and its code is tree-shaken out of production builds entirely).

That's it — same `ky` client, same Zod validation, same React Query hooks, same pages.
