# Fix Accept-Stash Navigation Bug

## Why

Closing the FE-testing-gaps goal surfaced a real SPA bug, currently
documented in `apps/web/tests/e2e/invitation-accept.spec.ts` as a
`.fixme()`:

When an invited user opens `/invitations/accept#t=<token>` BEFORE having
a Nica ERP account (the "stash" path), the SPA correctly previews the
invitation, stashes the token in `sessionStorage`, walks them through
`/signup → /confirm → /login`, and the post-login bootstrap pops the
stash and redirects them through `/invitations/accept` to redeem it.
The accept POST returns 200, the membership is created server-side, and
TanStack Query's hook-level `onSuccess` runs. But the route's
`mutate({ onSuccess })` callback — where `navigate({ to: "/dashboard" })`
lives — does NOT take effect; the page stays on `/invitations/accept`
rendering "Aceptando…" forever. The directly-authenticated entry path
covered by `member-management.spec.ts` does NOT hit this.

This is the canonical TanStack Query StrictMode footgun: the mutate-call
`onSuccess` is dropped when the surrounding component unmounts and
remounts in dev StrictMode mid-flight, while the hook-level onSuccess
survives. The fix is to move the navigation off the mutate callback and
onto a `useEffect` that watches `acceptMut.isSuccess` — the canonical
"mastering mutations" pattern.

## Definition of done

- `apps/web/src/routes/invitations/accept.tsx`: hash-flow `acceptMut.mutate`
  and paste-flow `submitPasted` no longer rely on a `mutate({ onSuccess })`
  callback for `navigate({ to: "/dashboard" }) + setPickerConfirmed()`;
  the same side-effects fire from a `useEffect` watching `isSuccess`.
- All existing unit + integration specs for the accept route stay green
  (none of them depend on the callback timing).
- `tests/e2e/invitation-accept.spec.ts` is flipped from `test.fixme()`
  back to `test()` and passes against the local stack.
- `tests/e2e/member-management.spec.ts` (the directly-authenticated
  entry path) still passes.
- `pnpm typecheck`, `pnpm lint`, full vitest run, and the @smoke
  Playwright suite stay green.

## Tasks

- [x] 1. Reproduce the bug live: start `pnpm dev` and run
  `tests/e2e/invitation-accept.spec.ts` with the `.fixme` removed; confirm
  the failure mode and capture the response/network log so we know the
  baseline.
- [x] 2. Refactor `AcceptInvitationRoute`: stop passing `onSuccess` to
  `acceptMut.mutate` in both the hash and paste paths; add a single
  `useEffect` watching `acceptMut.isSuccess` that calls
  `setPickerConfirmed()` then `navigate({ to: "/dashboard" })`. Keep the
  existing per-mode rendering branches untouched.
- [x] 3. Re-run `vitest run --project=integration tests/integration/routes/invitations-accept.spec.tsx`
  — the existing integration tests must still pass; adjust any mock
  that relied on the mutate callback firing synchronously.
- [x] 4. Flip `tests/e2e/invitation-accept.spec.ts` back to `test()`
  (drop `.fixme`) and run it against the local stack; iterate until
  green.
- [x] 5. Re-run `tests/e2e/member-management.spec.ts` to confirm the
  authed-link entry path is unaffected.
- [x] 6. Final sanity: `pnpm typecheck`, `pnpm lint`,
  `pnpm vitest run --coverage`, `pnpm playwright test --project=smoke`.
  Commit each meaningful step.

## Notes

- T1 ✓ flipped `.fixme()` → `test()` and reran against local stack:
  reproduced identically (30s timeout waiting for /dashboard; page
  stuck on "Aceptando…"). SPA runs under `React.StrictMode`
  (`apps/web/src/main.tsx`), which is consistent with the canonical
  "mutate-call onSuccess dropped after unmount/remount" footgun.
- T2 ✓ Root cause turned out to be deeper than the `mutate(onSuccess)`
  pattern: in the stash flow the `AcceptInvitationRoute` component
  mounts/unmounts THREE times in quick succession (router transitions
  during the auth/redirect chain), which tears down the `useMutation`
  observer each time and leaves the in-flight POST without a listener
  when the 200 lands. First attempt — moving navigation to a
  `useEffect` watching `isSuccess` — was insufficient because the
  observer itself never reaches `isSuccess`. Fix: lift the in-flight
  accept to a module-scoped dedup map keyed by token, fire
  `acceptInvitation()` directly, and let any remounted instance
  subscribe to the SAME promise via a listener set. Navigation runs
  from a `useEffect` watching the module-level status. Also
  invalidate `meQueryKey` so the route guard sees fresh
  `active_tenant` after the accept.
- T3 ✓ Integration spec rewritten: mocks `acceptInvitation` directly
  with a deferred promise helper and exercises the three states
  (pending → success → /dashboard nav; pending → reject → destructive
  alert). 7/7 pass; full vitest suite 280/280 with thresholds green.
- T4 ✓ Flipped `.fixme()` → `test()`. E2E now passes against the
  local stack in ~3.7s. Test was extended to drive the natural
  post-accept UX (transit /welcome to capture display_name, then the
  /tenants picker to select the empresa — both are pre-existing
  guard behaviour, not the bug under test).
- T5 ✓ `member-management.spec.ts` re-run green (no regression on the
  directly-authenticated entry path).
- T6 ✓ Final gates: `pnpm typecheck`, `pnpm lint`, vitest 280/280 with
  thresholds, smoke + invitation-accept critical + member-management
  critical all green.

## Final summary

Root cause: in the stash flow the accept route remounts several times
mid-request, destroying the component-bound `useMutation` observer
before the POST's response arrives. Fixed by lifting the in-flight
accept to a module-scoped dedup keyed by token so listeners attached
on remount still receive the result. Integration spec rewritten around
a deferred `acceptInvitation` promise. E2E `.fixme` → `test`; passes
in ~3.7s end-to-end.
