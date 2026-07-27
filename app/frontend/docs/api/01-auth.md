# Auth API

## Overview

Handles login and "who am I" for the whole app. Every other module's requests depend on the token this module produces — `RequireAuth` (`src/auth/RequireAuth.tsx`) blocks access to every page except `/login` and `/access` until a token exists.

**Backend status:** nothing exists yet. This needs a real identity/session system (even a simple one — username/password against a `users` table, or SSO, is fine as long as it returns the shape below).

**Consumed by:**
- `src/pages/LoginPage.tsx` → `src/components/LoginForm.tsx` → `src/hooks/useLoginForm.ts`
- `src/components/Sidebar.tsx` and `src/components/TopBar.tsx` (both show the logged-in user's name/initials)

**Frontend files:**
- Schema: `src/domains/auth/auth.schema.ts`
- API calls: `src/domains/auth/auth.api.ts`
- Hooks: `src/domains/auth/useLoginMutation.ts`, `src/domains/auth/useCurrentUserQuery.ts`
- Mock: `src/mocks/fixtures/auth.fixtures.ts`, `src/mocks/handlers/auth.handlers.ts`

---

## `POST /auth/login`

Exchanges a username/password for a bearer token.

**Auth required:** No.

**Request body**

```json
{
  "username": "j.doe@collectai.com",
  "password": "hunter2"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `username` | string | yes | Non-empty. Displayed on the login form as "Username or Employee ID" — accept whichever identifier your user table uses. |
| `password` | string | yes | Non-empty. |

**Success response — `200`**

```json
{
  "token": "eyJhbGciOi...",
  "user": {
    "name": "Budi Santoso",
    "role": "Regional Manager",
    "initials": "BS"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `token` | string | Opaque bearer token. Stored in `localStorage` (`src/auth/tokenStorage.ts`) and sent as `Authorization: Bearer <token>` on every subsequent request. |
| `user.name` | string | Full display name. |
| `user.role` | string | Display label under the name in the sidebar/topbar (e.g. job title). |
| `user.initials` | string | Short initials shown in the avatar circle (e.g. `"BS"`). |

**Error responses**

| Status | When | Frontend behavior |
|---|---|---|
| `401` | Bad credentials | Shows "Your session has expired. Please sign in again." under the form (this copy is a bit login-specific and worth revisiting once a backend exists — see note below). |
| any other non-2xx | Server error | Generic "Something went wrong" message. |

**Step-by-step: what happens after this call succeeds**
1. `useLoginMutation` (`src/domains/auth/useLoginMutation.ts`) stores `token` via `tokenStorage.setToken()`.
2. It immediately seeds React Query's cache for `GET /auth/me` with the `user` object from this same response — so the app doesn't need to make a second round-trip just to show the user's name right after login.
3. `useLoginForm` navigates to `/dashboard`.

---

## `GET /auth/me`

Returns the currently authenticated user. Used to populate the sidebar/topbar avatar, and as a general "is my token still valid" check.

**Auth required:** Yes.

**Request:** no body, no query params.

**Success response — `200`**

Same `user` shape as the `login` response, but as the top-level body (not nested):

```json
{
  "name": "Budi Santoso",
  "role": "Regional Manager",
  "initials": "BS"
}
```

**Error responses**

| Status | When | Frontend behavior |
|---|---|---|
| `401` | Token missing/expired/invalid | Token is cleared from `localStorage`, a global `auth:unauthorized` event fires, and the user is redirected to `/login` on their next render. |

**Notes**
- This query only runs when a token is present (`useCurrentUserQuery` checks `isAuthenticated` before firing — see `src/domains/auth/useCurrentUserQuery.ts`), so it won't spam an unauthenticated `/auth/me` call on the login screen.
- React Query caches this aggressively (`staleTime: 30s` app-wide default) — it does not refetch on every route change, only on mount if stale or after a manual invalidation.

## Open items for whoever builds the real backend

- **Error body format.** The frontend currently only branches on HTTP status code, not response body content (see the root [`README.md`](./README.md) conventions section). If you want your real `401`/`400` messages (e.g. "account locked", "password expired") to actually reach the user instead of a generic message, say so — it's a small addition to `src/api/apiError.ts` and `LoginForm.tsx` to read a `{ message: string }` error body once that contract is agreed.
- **Token refresh / expiry.** There is currently no refresh-token flow — a token is used until it 401s, at which point the user is simply logged out. If your backend issues short-lived tokens, either issue long-lived ones for now, or flag this so a refresh flow can be added.
- **"Remember this workstation" checkbox.** It exists in the UI (`LoginForm.tsx`) but is not currently wired to anything — decide with product/security whether it should extend token lifetime, and if so what `POST /auth/login` needs to accept/return to support that.
