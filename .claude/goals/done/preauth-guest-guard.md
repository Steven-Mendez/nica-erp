# Pre-auth Guest Guard

## Why

Today `authenticatedGuard()` (router.ts:50) sends unauthenticated users from
protected routes to `/login`, but there is no inverse: an authenticated user
who deep-links to `/login`, `/signup`, `/confirm`, `/forgot-password`, or
`/reset-password` lands on the form anyway. The user reports this causes
"many problems" (presumably double-submit edge cases, confusion about
session state, and breakage of the post-auth flow when the form posts with
an already-active session). The fix mirrors `indexRoute.beforeLoad`
(router.ts:60–80), which already handles the "authenticated → go to next
step" case for `/`.

## Definition of done

- A `guestGuard()` function exists in `apps/web/src/router.ts` that:
  redirects authenticated users to `nextRouteForCurrentState({ pathname:
  "/dashboard" })` (fallback `/dashboard`), honouring the pending-invite
  stash; no-op when there is no access token.
- The guard is wired into `beforeLoad` of `/login`, `/signup`, `/confirm`,
  `/forgot-password`, `/reset-password`.
- `indexRoute.beforeLoad` is refactored to call `guestGuard()` so the
  authenticated-redirect logic lives in one place.
- `pnpm typecheck`, `pnpm lint`, and `pnpm vitest run` for `apps/web` are
  green.
- Existing Playwright `auth.spec.ts @smoke` is unaffected (it visits
  `/login` unauthenticated).

## Tasks

- [x] 1. Add `guestGuard()` in `apps/web/src/router.ts` (after
  `authenticatedGuard`, ~line 58). Implements: no token → return; token +
  pending invite → redirect to `/invitations/accept#t=…`; token + no
  invite → redirect to `nextRouteForCurrentState({ pathname: "/dashboard"
  }) ?? "/dashboard"`.
- [x] 2. Refactor `indexRoute.beforeLoad` (router.ts:60–80) to: if no
  token → `redirect({ to: "/login" })`; else → `await guestGuard()`.
  Removes the duplicated stash/next logic.
- [x] 3. Wire `beforeLoad: guestGuard` on `loginRoute`, `signupRoute`,
  `confirmRoute`, `forgotPasswordRoute`, `resetPasswordRoute`.
- [x] 4. Run `pnpm --filter @nica/web typecheck && pnpm --filter @nica/web
  lint && pnpm --filter @nica/web vitest run`. Fix anything that breaks.

## Notes

- 2026-05-31 — Single-file change to `apps/web/src/router.ts`. Added
  `guestGuard()` mirroring `authenticatedGuard()` (handles pending-invite
  stash + `nextRouteForCurrentState` fallback to `/dashboard`).
  `indexRoute.beforeLoad` collapsed to `if no token → /login; else
  guestGuard()`. Wired `beforeLoad: guestGuard` on `loginRoute`,
  `signupRoute`, `confirmRoute`, `forgotPasswordRoute`,
  `resetPasswordRoute`.
- 2026-05-31 — Verification: `pnpm typecheck` ✓, `pnpm lint` ✓,
  `pnpm test:unit` 166/166 ✓ (incl. `route-guard.test.ts` 9/9),
  `pnpm test:integration` 114/114 ✓ (incl. `routes/confirm.spec.tsx` —
  the new guard does not break the unauthenticated render path because
  `getAccessToken()` is null under jsdom).
- 2026-05-31 — Not committed (left for the user per the no-auto-commit
  rule). E2E run not executed (would need the API stack up); existing
  `auth.spec.ts @smoke` is unaffected because it visits `/login` without
  a session.

## Summary

Authenticated users now bounce off `/login`, `/signup`, `/confirm`,
`/forgot-password`, `/reset-password`, and `/` to the right
post-onboarding screen (`/welcome` | `/onboarding` | `/tenants` |
`/dashboard`), respecting any stashed invitation token. One file
touched, zero new tests (the underlying `nextRouteForCurrentState` was
already covered, and adding a wrapper-level test would just re-assert
the same branches through a mocked `redirect`). Diff is ~30 lines of
net additions.
