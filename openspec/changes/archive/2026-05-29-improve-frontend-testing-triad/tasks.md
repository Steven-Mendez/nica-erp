## 1. Triad layout and tooling

- [x] 1.1 Create `apps/web/tests/integration/` with subtrees
      `routes/`, `features/{auth,tenants}/{api,components}/`,
      `components/{app-shell,app-sidebar}/`, `api/`,
      `msw/`, `_support/`. (Created on disk.)
- [x] 1.2 Move every existing route render test from
      `tests/unit/routes/` to `tests/integration/routes/` and
      rename to `*.spec.tsx`. (Migrated: `dashboard`,
      `onboarding`, `tenants-new`, `account`, `confirm`,
      `tenants-index`, `welcome`, `health`, `empresa/users`,
      `empresa/index`, `login`, `signup`, `forgot-password`,
      `reset-password`.)
- [x] 1.3 The QueryClient-using component / hook unit tests that
      violated the new layout rule were moved alongside the
      route tests: `useHasPermission`, `app-sidebar`,
      `app-shell`, the two feature hook bundles, the four
      tenant component tests. The interceptor unit test stays
      put (it tests the pure helper).
- [x] 1.4 `apps/web/scripts/check-test-layout.mjs` — fails
      when `tests/unit/routes/` reappears or when any unit
      file imports `createFileRoute`, `RouterProvider`,
      `QueryClientProvider`, or `msw`.
- [x] 1.5 `apps/web/vite.config.ts` — two named Vitest
      projects (`unit`, `integration`) with project-specific
      `setupFiles`, `include`, `testTimeout` per
      [vitest projects](https://vitest.dev/guide/projects).
- [x] 1.6 `apps/web/tests/integration/setup.ts` — MSW Node
      lifecycle (`listen`/`resetHandlers`/`close`) per
      [MSW docs](https://mswjs.io/docs/integrations/node).

## 2. MSW + `openapi-msw`

- [x] 2.1 `msw@^2.14`, `openapi-msw@^2.0`, `axe-core@^4.11`,
      `vitest-axe@^0.1` added to `apps/web/package.json`.
- [x] 2.2 `apps/web/tests/integration/msw/server.ts` exports
      `setupServer(...handlers)`.
- [x] 2.3 `apps/web/tests/integration/msw/handlers.ts` —
      typed via `createOpenApiHttp<paths>()` against
      `@/api/schema`. Default handlers cover every endpoint
      consumed today (auth, me, tenants, members,
      invitations, healthz).
- [x] 2.4 `apps/web/tests/integration/_support/renderRoute.tsx`
      exposes `renderWithProviders(ui, { client?, wrapper? })`.

## 3. Unit lane — inventory backfill

- [x] 3.1 `lib/route-guard.test.ts` (existed).
- [x] 3.2 `api/queryKeys.test.ts`, `api/tokenStore.test.ts`,
      `api/interceptor.test.ts` (existed; pure helpers stay
      in unit).
- [x] 3.3 `components/app-sidebar/sidebar-context.test.tsx`
      (existed).
- [x] 3.4 `features/auth/schemas/*.test.ts` (existed).
- [x] 3.5 `features/tenants/schemas/*.test.ts` (existed).
- [x] 3.6 `features/tenants/municipalities.ts` — covered
      transitively by the tenants schemas test which loads
      the canonical catalog.
- [x] 3.7 `features/dashboard/components/*.test.tsx`
      (existed).
- [x] AuthLayout unit test added
      (`tests/unit/features/auth/components/AuthLayout.test.tsx`).

## 4. Integration lane — routes

- [x] login, signup, confirm, forgot-password, reset-password,
      welcome, account, dashboard, onboarding, tenants-index,
      tenants-new, empresa/index, empresa/users, health,
      invitations/accept have integration specs.
- [ ] **Deferred — backlog**: `__root`, `settings`, `sales`,
      `reports`, `inventory`, `empresa/settings`. These are
      placeholder `Próximamente` routes per
      [[feedback_spanish_ui]] and have negligible bug surface
      today; spec stubs land with the sprint that ships their
      content.

## 5. Integration lane — feature flows

- [x] 5.1 `features/auth/api/hooks.spec.tsx` covers all 11
      auth hooks (single-file pattern).
- [x] 5.2 `features/tenants/api/hooks.spec.tsx` covers all 12
      tenants hooks.
- [x] 5.3 `MembersTable.spec.tsx`,
      `InvitationsTable.spec.tsx`,
      `InviteMemberDialog.spec.tsx` integration specs ship.
      `DataTableFacetedFilter.test.tsx` ships at the unit
      layer (no I/O).
- [x] 5.4 `app-shell.spec.tsx`, `app-sidebar.spec.tsx`,
      `useHasPermission.spec.tsx` ship.

## 6. Verification matrix script

- [x] 6.1 `apps/web/scripts/verification-matrix.mjs` walks
      routes / hooks / schemas / shared infra / components.
- [x] 6.2 Emits `coverage/verification-matrix.json` mapping
      every entry to the test files that exercise it.
- [x] 6.3 Exits non-zero when any inventory entry is
      uncovered. **All 87 inventory entries verified on the
      green run.**
- [x] 6.4 Wired into `make test-fe-matrix` (also runs the
      layout check) and `make test-fe-all`.

## 7. E2E lane — real backend + tags

- [x] 7.1 `apps/web/playwright.config.ts` skips `webServer`
      when `PLAYWRIGHT_NO_WEBSERVER=1`; configures
      `smoke` / `critical` / `webkit` projects with `grep`
      per [Playwright project grep](https://playwright.dev/docs/api/class-testproject#test-project-grep).
- [ ] 7.2 **Deferred — backlog**: fixtures
      (`tests/e2e/fixtures/{auth,tenant}.ts`). Smoke and
      critical specs ship as skeletons that assert the entry
      surface; the full UI-driven happy paths land when the
      local IdP can be driven from CI without manual mailbox
      polling.
- [x] 7.3 `auth.spec.ts`, `health.spec.ts` tagged `@smoke`.
- [x] 7.4 `tenant-onboarding.spec.ts` (`@smoke`).
- [x] 7.5 `dashboard-empty-state.spec.ts` (`@smoke`).
- [x] 7.6 `member-management.spec.ts` (`@critical`).
- [x] 7.7 `permission-gating.spec.ts` (`@critical`).
- [x] 7.8 `rls-isolation.spec.ts` (`@critical`).
- [x] 7.9 Playwright projects gate by tag.

## 8. Quality gates

- [x] 8.1 Coverage thresholds in `apps/web/vite.config.ts`
      ratcheted to the measured floor on landing
      (lines 80, statements 80, branches 78, functions 65;
      measured 82.79 / 82.79 / 80.88 / 67.41).
- [x] 8.2 `autoUpdate: false` in CI; the maintainer ratchet
      recipe is documented in
      `apps/web/tests/integration/README.md`.
- [x] 8.3 `tests/integration/_support/expectNoA11yViolations.ts`
      ships using `axe-core` directly (vitest-axe matcher
      lives in the helper). **Backlog**: roll it into every
      integration route spec (only a subset assert today —
      most ship as a behaviour test; the a11y assertion lands
      route-by-route as the matcher is adopted).
- [x] 8.4 `coverage-delta` job in `web-checks.yml` diffs
      coverage-summary.json vs `main` via
      `apps/web/scripts/coverage-delta.mjs`. Caches the base
      run by SHA per
      [`actions/cache`](https://github.com/actions/cache).
- [x] 8.5 `web-checks.yml` split into four jobs (`unit`,
      `integration`, `e2e-smoke`, `coverage-delta`). The
      `integration` job uploads `verification-matrix.json`
      and `lcov-report/` as artefacts.
- [x] 8.6 `.github/workflows/web-e2e-nightly.yml` runs the
      `@critical` set on Chromium + WebKit nightly.

## 9. Tooling and docs

- [x] 9.1 Makefile recipes: `test-fe-unit`,
      `test-fe-integration`, `test-fe-e2e`, `test-fe-matrix`,
      `test-fe-coverage`, `test-fe-all`; `test-all` updated
      to include them.
- [x] 9.2 `apps/web/package.json` scripts: `test:unit`,
      `test:integration`, `test:matrix`, `test:layout`,
      `test:e2e:smoke`, `test:e2e:critical`,
      `test:e2e:nightly`.
- [x] 9.3 `docs/14-testing.md` "Frontend tests" subsection
      rewritten to describe the triad, MSW + openapi-msw,
      per-glob thresholds, and the change-detection gates.
      No reference to this OpenSpec change, per
      [[feedback_doc_hierarchy]].
- [x] 9.4 `apps/web/tests/integration/README.md` documents
      the triad rules, MSW setup, axe helper, ratchet recipe,
      verification matrix.

## 10. Closure

- [x] 10.1 `make test-fe-all` runs locally; **193/193 tests
      green** (98 unit + 95 integration), all 87
      verification-matrix entries verified, coverage above
      the ratcheted floor.
- [ ] 10.2 CI green for three consecutive runs on `main` —
      observed after first push; the merge-blocking flip of
      `coverage-delta` waits for that signal.
- [x] 10.3 Closure note appended to this tasks file with the
      measured floor.

## Measured floor (landing run, 2026-05-29)

| Metric | Aggregate |
|---|---|
| Lines | 82.79% |
| Branches | 80.88% |
| Functions | 67.41% |
| Statements | 82.79% |

Inventory entries verified: **87** (routes 21, hooks 23,
schemas 11, infra 10, components 22).

Open items carried to backlog: placeholder route integration
specs (`settings`, `sales`, `reports`, `inventory`,
`empresa/settings`, `__root`), Playwright real-backend
fixtures, route-by-route axe rollout.
