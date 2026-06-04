# Design — fix-unauth-401-interceptor

## Problem

`fetchWithAuth` (`apps/web/src/api/interceptor.ts:142-166`) handles two
distinct failure modes through one code path:

1. **Authenticated 401**: the operator's access token was rejected.
   The session is genuinely lost; the SPA should clear the token
   store, navigate to `/login`, and let the operator sign in again.
2. **Unauthenticated 401**: a public endpoint (signup, OTP confirm,
   password forgot, password reset) returned 401 because the *input*
   was wrong — wrong code, used token, bad credentials. There was no
   session, so there is nothing to "lose."

Today both paths fire `handleAuthLost()`. The auth-lost callback
navigates to `/login`, which is harmless when the operator is already
authenticated and bouncing on a stale token, but catastrophic on
`/confirm` and `/reset-password`: the SPA navigates away *before* the
route component renders the inline error, so the operator sees no
feedback at all.

The audit on 2026-06-03 reproduced this end-to-end with a wrong OTP.

## Design

### Single discriminator: was a bearer token attached?

`attachAuth` already conditionally attaches the bearer:

```ts
const attachAuth = (input, init) => {
  const token = getAccessToken();
  if (token === null) return init;       // ← no bearer attached
  // ... otherwise set Authorization header
};
```

The information "no bearer was attached" is currently discarded. The
fix surfaces it on the wrapping init via an internal flag:

```ts
interface RetriableInit extends RequestInit {
  __authRetried?: boolean;
  __bearerAttached?: boolean;  // new
}
```

`attachAuth` returns `{ ...init, headers, __bearerAttached: true }`
when it sets the Authorization header, and the unchanged `init`
(with `__bearerAttached` undefined / false) when the token store is
empty.

### Branched 401 handler

```ts
const first = await fetch(input, attachAuth(input, init));
if (first.status !== 401) return first;

// 401 — distinguish session loss from "bad input on a public endpoint".
const initWithFlag = attachAuth(input, init);
if (initWithFlag.__bearerAttached !== true) {
  // No bearer attached; this 401 is the endpoint speaking, not auth.
  return first;
}

// existing retry-once + handleAuthLost branch below, unchanged
if (init.__authRetried === true) { handleAuthLost(); return first; }
...
```

The retry-once path (refresh, retry with new bearer) only runs for
the bearer-attached branch. The `__authRetried` guard already gates
retries.

### Why not call `rawFetch` from the auth endpoints?

The auth endpoints (`register`, `confirmSignup`, etc.) could in
principle switch to `rawFetch` directly. That avoids the interceptor
entirely. We **chose not to** because:

- It splits the auth-wrapping logic across two code paths. Any future
  cross-cutting concern (logging, telemetry, CORS preflight tweaks)
  has to be added in two places.
- It puts the "this endpoint is unauthenticated" knowledge in each
  endpoint definition rather than in the interceptor where it
  belongs.
- The `__bearerAttached` discriminator is local to the interceptor
  and survives future endpoint refactors automatically.

### Refresh path: still bearer-only

The refresh call inside `tryRefresh()` already uses `rawFetch`
directly (`rawFetch` does not invoke `fetchWithAuth`), so a 401 on
`POST /v1/auth/refresh` does not loop through this branch. No change
needed there.

### `bootRefresh` at app boot

`bootRefresh` consumes a persisted refresh token (sessionStorage) and
exchanges it for an access token before the router mounts. It uses
`tryRefresh()` → `rawFetch`. Same — no change.

## Alternatives considered

### Alt 1: tag every endpoint with `{ unauthenticated: true }`

Touches every endpoint definition and requires call-site discipline
forever. Easy to forget on a new endpoint and easy to misuse on an
authenticated endpoint that legitimately returns 401.

### Alt 2: only redirect when refresh has been attempted

That is what today's code already implies (refresh runs before
handleAuthLost), but the refresh itself is conditional on a refresh
token being present — and no-bearer requests typically have no
refresh token either, so refresh fails immediately and the redirect
still fires. This alternative would not fix the bug.

### Alt 3: catch the redirect at the route level

The route component could detect that the 401 is the route's own
mutation error and rewrite the upcoming navigation. That is exactly
the kind of cross-cutting policy this layer is supposed to centralise;
piling it into route components is the long road to inconsistency.

## Test coverage

`apps/web/tests/unit/api/interceptor.test.ts` already covers the
authenticated-401 paths. The new cases assert the unauthenticated
branch:

- **no bearer in store + 401** → response returned, `onAuthLost` not
  called, `tryRefresh` not invoked.
- **bearer in store + 401 + refresh fails** → `onAuthLost` called
  (existing behaviour preserved).
- **bearer in store + 401 + refresh succeeds + retry 200** →
  retried response returned (existing behaviour preserved).

## Risks / failure modes

- **A pre-existing endpoint that genuinely depends on the redirect
  for unauthenticated 401s.** Surveyed; the only such consumer is
  `useMeQuery`, which is *enabled* only when an access token exists
  (see `useMeQuery` in `features/auth/api/hooks.ts`), so it cannot
  hit the new branch in practice.
- **A future endpoint that adds bearer headers manually**, bypassing
  `attachAuth`. Out of scope; if it happens, the `__bearerAttached`
  flag stays false and the 401 becomes passthrough. That is a
  defensible default — the caller knows the request was
  unauthenticated.

## Out of scope

- Re-architecting the `onAuthLost` callback. The router shell still
  owns the redirect target; the interceptor only fires it less often.
- Surfacing better Spanish copy for unauthenticated 401s. That is
  already covered by `frontend-auth-error-feedback`'s
  `messageForProblem` registry; this change makes that copy actually
  reach the user.
