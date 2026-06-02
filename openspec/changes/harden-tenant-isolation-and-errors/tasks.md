## 1. Cache isolation on identity change

- [ ] 1.1 Update `useLogoutMutation` in `apps/web/src/features/auth/api/hooks.ts` so the `onSettled` callback runs `clear()` (token store), then `clearPickerConfirmed()`, then `qc.clear()` — in that order.
- [ ] 1.2 Add a Vitest integration test under `apps/web/tests/integration/auth-logout-clears-cache.test.tsx` proving that after logout, no cached `["tenant", …]` keys remain.
- [ ] 1.3 Add a Vitest integration test under `apps/web/tests/integration/cross-operator-no-leak.test.tsx` simulating operator A logout → operator B login on the same `QueryClient`, asserting B's members table never renders A's rows.

## 2. Stale-tenant guard on per-tenant queries

- [ ] 2.1 In `apps/web/src/features/tenants/api/hooks.ts`, refactor `useTenantQuery`, `useMembersQuery`, and `useInvitationsQuery` so each reads `useMeQuery().data?.active_tenant` and gates `enabled` on `tenantId !== "" && tenantId === activeTenant`.
- [ ] 2.2 Update the file-level comment that currently describes the namespace strategy to note the active-tenant guard.
- [ ] 2.3 Add a Vitest integration test under `apps/web/tests/integration/stale-tenant-guard.test.tsx` that flips `me.active_tenant` mid-render and asserts no request is issued to the prior tenant id.
- [ ] 2.4 Regression-check existing tenant-flow integration tests (run the full Vitest suite) to confirm the new guard does not break the picker or onboarding routes.

## 3. Root-level error & not-found components

- [ ] 3.1 Create `apps/web/src/components/error-fallback/route-forbidden-card.tsx` — Spanish copy, authentication-aware recovery link via synchronous `getAccessToken()`.
- [ ] 3.2 Create `apps/web/src/components/error-fallback/route-not-found-card.tsx`.
- [ ] 3.3 Create `apps/web/src/components/error-fallback/route-schema-error-card.tsx`.
- [ ] 3.4 Create `apps/web/src/components/error-fallback/route-runtime-error-card.tsx`.
- [ ] 3.5 Create `apps/web/src/components/error-fallback/dispatch.tsx` — a `dispatchRouteError(error)` helper that returns the correct card by inspecting `ApiProblem.status` / `instanceof ZodError` / fallthrough.
- [ ] 3.6 Wire `errorComponent` and `notFoundComponent` on `rootRoute` in `apps/web/src/routes/__root.tsx` to render the bare-shell variant via the dispatch helper.

## 4. AppShell in-shell error boundary

- [ ] 4.1 Identify the AppShell wrapper route (`apps/web/src/routes/_app.tsx` or the route group housing `/empresa/*`, `/dashboard`, etc.) and attach an `errorComponent` that renders the dispatch helper **inside** the shell.
- [ ] 4.2 Confirm `rootRoute.errorComponent` only fires for failures escaping the AppShell (manual smoke + a Vitest test that throws inside an AppShell child and asserts the shell chrome remains mounted).

## 5. Test coverage for error boundaries

- [ ] 5.1 Vitest test: route loader throws `ApiProblem(403)` → `RouteForbiddenCard` renders, sidebar visible.
- [ ] 5.2 Vitest test: route loader throws `ZodError` → `RouteSchemaErrorCard` renders with the documented Spanish copy.
- [ ] 5.3 Vitest test: route loader throws a generic `Error` → `RouteRuntimeErrorCard` renders.
- [ ] 5.4 Vitest test: navigate to `/foobar` → `RouteNotFoundCard` renders.
- [ ] 5.5 Vitest test: fallback render does not produce a fetch (MSW handler asserts zero hits on `/v1/me`).
- [ ] 5.6 Vitest test: unauthenticated token-store state routes the recovery button to `/login`; authenticated state routes it to `/dashboard`.

## 6. Documentation

- [ ] 6.1 Update `docs/09-frontend.md` with a short subsection "Query-client lifecycle" describing the logout-clear contract and the per-tenant stale-id guard. No reference to `openspec/changes/*`.
- [ ] 6.2 Update `docs/09-frontend.md` (or the existing routing section) with a short subsection "Route error fallbacks" listing the four categories and which card handles each.

## 7. Verification

- [ ] 7.1 Run `pnpm --filter web typecheck` — passes.
- [ ] 7.2 Run `pnpm --filter web test` (unit + integration) — all green.
- [ ] 7.3 Manual smoke: log in as operator A, navigate to `/empresa/usuarios`, log out, log in as operator B, confirm operator B's members render with no flash of A's data.
- [ ] 7.4 Manual smoke: as operator A on `/empresa/usuarios`, have another browser session remove operator A from the empresa, then click a row — confirm the in-shell `RouteForbiddenCard` renders without losing the sidebar.
- [ ] 7.5 Manual smoke: navigate to `/foobar` while authenticated — confirm `RouteNotFoundCard` renders inside the AppShell with the `Volver al inicio` button routing to `/dashboard`.
