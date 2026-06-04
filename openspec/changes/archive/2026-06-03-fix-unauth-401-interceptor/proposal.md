## Why

The single-retry 401 interceptor at `apps/web/src/api/interceptor.ts`
unconditionally treats every 401 as "session lost." It first tries a
refresh; when refresh fails (or no refresh token is present) it calls
`handleAuthLost()`, which clears the in-memory token store and invokes
the registered `onAuthLost` callback. The router shell registers a
callback that navigates the SPA to `/login`.

That behaviour is correct for an *authenticated* request whose access
token was rejected. But every API call — including the public
endpoints `POST /v1/auth/register`,
`POST /v1/auth/confirm-signup`,
`POST /v1/auth/password/forgot`,
`POST /v1/auth/password/reset`, and the auth refresh wrapper itself
indirectly — flows through the same `fetchWithAuth` wrapper. For those
endpoints, a 401 simply means the *input* was wrong (bad credentials,
wrong OTP, used reset token). There is no session to lose, so a
redirect to `/login` is incorrect — and it *also* races
`FormErrorAlert`'s render: by the time the route component receives
the `mutation.error` from the failed call, the SPA has already
navigated away from `/confirm` (or `/reset-password`), so the user
sees nothing.

The 2026-06-03 in-browser audit reproduced this end-to-end on
`/confirm`: a wrong OTP returned `401` and the SPA silently sent the
operator to `/login` with no toast, no alert, and no document title
change. The same bug applies to any unauthenticated-endpoint 401 — the
audit only exercised OTP, but a used password-reset token has the
same shape.

This change tightens `fetchWithAuth` so that the auth-lost branch
only fires when the original request *carried* a bearer token. 401s
from no-bearer requests are now passthrough errors that the calling
mutation can surface via `FormErrorAlert`, with no global side
effects.

## What Changes

### Interceptor — distinguish bearer-attached vs unauthenticated 401s

- `apps/web/src/api/interceptor.ts`:
  - `attachAuth` already conditionally attaches the bearer when an
    access token is present in the in-memory store. Today the
    information that no bearer was attached is discarded; capture it
    on the wrapping init.
  - Introduce an internal flag `__bearerAttached?: boolean` on the
    existing `RetriableInit` interface. `attachAuth` sets it to
    `true` only when `getAccessToken() !== null` (i.e. when the
    final headers include `Authorization: Bearer …`). When no
    bearer was attached, the flag stays `false`/undefined.
  - On 401, branch on the flag:
    - **bearer was attached** → existing behaviour (try refresh,
      retry once, otherwise `handleAuthLost()`).
    - **no bearer attached** → return the 401 response as-is.
      Never refresh. Never invoke `handleAuthLost`. The calling
      endpoint surfaces the error to its mutation.
  - Document the new flag inline so a future reader does not
    flatten the branch back into "every 401 means auth lost."

### Endpoints — keep using the typed client

- No surface changes to `apps/web/src/features/auth/api/endpoints.ts`.
  The auth endpoints continue to call `api.POST` / `api.GET` (which
  flow through `fetchWithAuth`). The interceptor change is enough on
  its own; we deliberately do **not** carve a `rawFetch` exception
  per-endpoint because that would split the auth wrapping logic
  across two code paths.

### Tests

- `apps/web/tests/unit/api/interceptor.test.ts` — extend with the
  new cases below. The existing harness already covers (a) 200
  passthrough, (b) 401 + successful refresh + retry, and (c) 401 +
  failed refresh → handleAuthLost. Add:
  - 401 from a request that never carried a bearer (no token in
    store, or pre-stripped) → response returned, `onAuthLost` never
    fired, no refresh attempt made.
  - 401 from a request whose bearer was stripped manually via the
    `__bearerAttached=false` opt-out (defensive — covers
    `confirmSignup` even if a token were somehow present).

### Smoke

- Browser smoke on `/confirm`: wrong OTP renders the inline
  `FormErrorAlert` and stays on the route.
- Browser smoke on `/reset-password`: used token renders the
  inline alert and stays on the route.

## Capabilities

### New Capabilities

- `frontend-auth-interceptor`: the single 401-retry wrapper around
  `fetch` for the SPA, including the rule that 401s from
  unauthenticated requests do not trigger the "session lost"
  redirect. This capability codifies a piece of frontend shell
  infrastructure that has been implicit until now.

## Impact

- Affected code:
  - `apps/web/src/api/interceptor.ts` — add `__bearerAttached`
    flag, branch the 401 handler, update inline docs.
- Affected tests:
  - `apps/web/tests/unit/api/interceptor.test.ts` — two new
    scenarios.
- Affected docs:
  - `docs/sprints/03-tenants-and-rls.md` — append a "Sprint
    follow-up — fix global 401 interceptor on unauth endpoints
    (2026-06-03)" subsection.
  - No ADR. The fix is a behavioural correction within an
    already-decided architecture (in-memory tokens + single retry).
- Affected dependencies: none.
- Affected env: none.
- Affected backend: none. The fix is purely in the SPA's fetch wrapper.
- Out of scope:
  - Migrating individual auth endpoints to a `rawFetch` exception.
  - Re-architecting `onAuthLost` callbacks or moving them out of
    the interceptor.
  - The minor "translate `accountant` → `Contador` in the
    invitations table" item from the same audit — handled in a
    follow-up commit, not this change.
  - The one-line `isSubmitting` patch on
    `apps/web/src/routes/tenants/new.tsx` — already in the working
    tree from the audit session, committed alongside this change
    but not part of the spec delta (no behavioural requirement
    captured; it was a typo).
