## ADDED Requirements

### Requirement: `features/auth/` feature slice with six routes

The SPA SHALL ship `apps/web/src/features/auth/` (Zod schemas, hooks,
components) plus the routes `/signup`, `/confirm`, `/login`,
`/forgot-password`, `/reset-password`, and `/me` under
`apps/web/src/routes/`. Each route SHALL be a `createFileRoute(...)`
that uses the generated TanStack Query hooks against the typed
`openapi-fetch` client. Cross-feature imports from `features/auth/`
into other feature slices SHALL remain forbidden by ESLint per
[`docs/09-frontend.md` §No cross-feature imports](../../../../docs/09-frontend.md#1-no-cross-feature-imports).

#### Scenario: Auth routes are reachable in dev

- **WHEN** `pnpm dev` is run and the user navigates to
  `http://localhost:5173/signup`, `/confirm`, `/login`,
  `/forgot-password`, `/reset-password`, `/me`
- **THEN** each route SHALL render its top-level component without
  console errors

### Requirement: In-memory-only token store

The SPA SHALL hold the access token, refresh token, and id token in a
**module-scoped closure** (not React state, not Zustand persist, not
`localStorage`, not `sessionStorage`, not a cookie). The store SHALL
expose `getAccessToken()`, `getRefreshToken()`, `setTokens({access,
refresh, id})`, and `clear()`. A page reload SHALL cause the tokens
to be lost.

#### Scenario: Reload clears the session

- **WHEN** a logged-in SPA user reloads the page
- **THEN** `getAccessToken()` SHALL return `null` and the next
  authenticated request SHALL produce a 401 followed by a redirect
  to `/login`

#### Scenario: Tokens are not persisted to web storage

- **WHEN** a logged-in user inspects `localStorage` and
  `sessionStorage`
- **THEN** neither storage SHALL contain any key whose value matches
  the active JWT

### Requirement: Single-retry 401 interceptor on the HTTP client

The `openapi-fetch` client SHALL install an interceptor that, on a
401 response, calls `POST /v1/auth/refresh` **exactly once** with the
in-memory refresh token, updates the in-memory tokens on success, and
retries the original request **exactly once**. If the refresh call
itself returns non-2xx, or the retried request returns 401 again, the
interceptor SHALL `clear()` the token store and `navigate('/login')`.
The interceptor MUST NOT loop indefinitely on consecutive 401s.

#### Scenario: 401 → refresh → retry succeeds

- **WHEN** an authenticated request returns 401, `POST
  /v1/auth/refresh` returns 200 with fresh tokens, and the retried
  request returns 200
- **THEN** the SPA SHALL surface only the final 200 to the calling
  hook

#### Scenario: Refresh failure routes to `/login`

- **WHEN** an authenticated request returns 401 and the subsequent
  `POST /v1/auth/refresh` returns 401
- **THEN** the token store SHALL be cleared and the router SHALL
  navigate to `/login`

#### Scenario: No infinite loop on repeated 401s

- **WHEN** every request and refresh returns 401
- **THEN** the SPA SHALL issue at most one refresh attempt and one
  retry before navigating to `/login`

### Requirement: `GET /v1/me` powers a current-user query

The `/me` route and the global header SHALL read the current user
from a single TanStack Query `useMeQuery()` that calls `GET /v1/me`.
The query SHALL be disabled when `getAccessToken()` returns `null` so
the unauthenticated state does not trigger an immediate request.

#### Scenario: `useMeQuery` is disabled without a token

- **WHEN** the SPA mounts on the `/login` route with no token in
  memory
- **THEN** the network panel SHALL NOT show a request to `/v1/me`
