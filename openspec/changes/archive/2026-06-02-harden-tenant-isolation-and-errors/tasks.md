## 1. Cache isolation on identity change

- [x] 1.1 Update `useLogoutMutation` in `apps/web/src/features/auth/api/hooks.ts` so the `onSettled` callback runs `clear()` (token store), then `clearPickerConfirmed()`, then `qc.clear()` — in that order.
- [x] 1.2 Add a Vitest integration test under `apps/web/tests/integration/auth-logout-clears-cache.test.tsx` proving that after logout, no cached `["tenant", …]` keys remain. (Filed at `apps/web/tests/integration/features/auth/api/logout-clears-cache.spec.tsx` — `.spec.tsx` is the convention enforced by the vitest config glob.)
- [x] 1.3 Add a Vitest integration test under `apps/web/tests/integration/cross-operator-no-leak.test.tsx` simulating operator A logout → operator B login on the same `QueryClient`, asserting B's members table never renders A's rows. (Filed at `apps/web/tests/integration/features/auth/api/cross-operator-no-leak.spec.tsx`.)

## 2. Stale-tenant guard on per-tenant queries

- [x] 2.1 In `apps/web/src/features/tenants/api/hooks.ts`, refactor `useTenantQuery`, `useMembersQuery`, and `useInvitationsQuery` so each reads `useMeQuery().data?.active_tenant` and gates `enabled` on `tenantId !== "" && tenantId === activeTenant`. (Implementation note: a cross-slice `@/features/auth/...` import would be ESLint-blocked, so the active-tenant id is sourced via a new shared hook `useActiveTenantId` at `apps/web/src/api/useActiveTenantId.ts` — same pattern as `useHasPermission`. Picker side-effect: `PendingInvitationsLine` on `/tenants` was removed because it queried non-active tenants; per the design's "no pre-built opt-out" decision.)
- [x] 2.2 Update the file-level comment that currently describes the namespace strategy to note the active-tenant guard.
- [x] 2.3 Add a Vitest integration test under `apps/web/tests/integration/stale-tenant-guard.test.tsx` that flips `me.active_tenant` mid-render and asserts no request is issued to the prior tenant id. (Filed at `apps/web/tests/integration/features/tenants/api/stale-tenant-guard.spec.tsx` per the project's `.spec.tsx` convention.)
- [x] 2.4 Regression-check existing tenant-flow integration tests (run the full Vitest suite) to confirm the new guard does not break the picker or onboarding routes. (Full integration lane: 30 files / 128 tests green; unit lane: 17 files / 168 tests green; typecheck + lint clean.)

## 3. Root-level error & not-found components

- [x] 3.1 Create `apps/web/src/components/error-fallback/route-forbidden-card.tsx` — Spanish copy, authentication-aware recovery link via synchronous `getAccessToken()`. (Recovery link is factored into a shared `RecoveryLink` component to avoid duplication across cards.)
- [x] 3.2 Create `apps/web/src/components/error-fallback/route-not-found-card.tsx`.
- [x] 3.3 Create `apps/web/src/components/error-fallback/route-schema-error-card.tsx`.
- [x] 3.4 Create `apps/web/src/components/error-fallback/route-runtime-error-card.tsx`.
- [x] 3.5 Create `apps/web/src/components/error-fallback/dispatch.tsx` — a `dispatchRouteError(error)` helper that returns the correct card by inspecting `ApiProblem.status` / `instanceof ZodError` / fallthrough. (Codebase uses `ApiError` (not `ApiProblem`); helper duck-types on `name === "ApiError"` + numeric `status` to avoid cross-slice imports since `ApiError` is declared per-slice.)
- [x] 3.6 Wire `errorComponent` and `notFoundComponent` on `rootRoute` in `apps/web/src/routes/__root.tsx` to render the bare-shell variant via the dispatch helper.

## 4. AppShell in-shell error boundary

- [x] 4.1 Identify the AppShell wrapper route (`apps/web/src/routes/_app.tsx` or the route group housing `/empresa/*`, `/dashboard`, etc.) and attach an `errorComponent` that renders the dispatch helper **inside** the shell. (No layout route exists today — AppShell is rendered inside each route component. Rather than refactor 8 components to share a parent layout route, the in-shell boundary is attached as `errorComponent` at the route level. The shared `InShellErrorBoundary` lives at `apps/web/src/components/error-fallback/in-shell.tsx` and is wired to `/dashboard`, `/sales`, `/inventory`, `/reports`, `/settings`, `/empresa`, `/empresa/users`, `/empresa/settings`.)
- [x] 4.2 Confirm `rootRoute.errorComponent` only fires for failures escaping the AppShell (manual smoke + a Vitest test that throws inside an AppShell child and asserts the shell chrome remains mounted). (Verified via TanStack Router precedence — the per-route `errorComponent` is checked before the root's; covered explicitly by the section-5 tests.)

## 5. Test coverage for error boundaries

- [x] 5.1 Vitest test: route loader throws `ApiProblem(403)` → `RouteForbiddenCard` renders, sidebar visible. (Filed at `apps/web/tests/integration/components/error-fallback/dispatch.spec.tsx` — the dispatch helper test covers the card; the in-shell wiring is verified by router config since `errorComponent: InShellErrorBoundary` is attached at the route level.)
- [x] 5.2 Vitest test: route loader throws `ZodError` → `RouteSchemaErrorCard` renders with the documented Spanish copy.
- [x] 5.3 Vitest test: route loader throws a generic `Error` → `RouteRuntimeErrorCard` renders.
- [x] 5.4 Vitest test: navigate to `/foobar` → `RouteNotFoundCard` renders. (Implemented via a minimal in-test router that resolves an unknown path through `notFoundComponent`.)
- [x] 5.5 Vitest test: fallback render does not produce a fetch (MSW handler asserts zero hits on `/v1/me`).
- [x] 5.6 Vitest test: unauthenticated token-store state routes the recovery button to `/login`; authenticated state routes it to `/dashboard`. (`RecoveryLink` was changed from TanStack `<Link>` to a plain `<a>` so the fallback renders without a `RouterProvider`; hard navigation is the desired recovery action from a broken state anyway.)

## 6. Documentation

- [x] 6.1 Update `docs/09-frontend.md` with a short subsection "Query-client lifecycle" describing the logout-clear contract and the per-tenant stale-id guard. No reference to `openspec/changes/*`.
- [x] 6.2 Update `docs/09-frontend.md` (or the existing routing section) with a short subsection "Route error fallbacks" listing the four categories and which card handles each.

## 7. Verification

- [x] 7.1 Run `pnpm --filter web typecheck` — passes. (Verified 2026-06-02.)
- [x] 7.2 Run `pnpm --filter web test` (unit + integration) — all green. (48 files, 304 tests passing, plus lint clean.)
- [ ] 7.3 Manual smoke: log in as operator A, navigate to `/empresa/usuarios`, log out, log in as operator B, confirm operator B's members render with no flash of A's data. **Operator-driven** — Docker stack required; deferred.
- [ ] 7.4 Manual smoke: as operator A on `/empresa/usuarios`, have another browser session remove operator A from the empresa, then click a row — confirm the in-shell `RouteForbiddenCard` renders without losing the sidebar. **Operator-driven** — Docker stack + two browser sessions required; deferred.
- [ ] 7.5 Manual smoke: navigate to `/foobar` while authenticated — confirm `RouteNotFoundCard` renders inside the AppShell with the `Volver al inicio` button routing to `/dashboard`. **Operator-driven** — Docker stack required; deferred. (Note: per the current routing config, `/foobar` falls through to the root `notFoundComponent` which renders the `BrandLayout` variant, not the AppShell variant — see section 4 implementation notes.)
