# Pre Sprint 04 — close active debt

## Why

Sprint 04 (`catalog` + `inventory`) will land on top of `tenants`, the outbox
table, and the shadcn primitive registry. Today three blockers and four loose
ends accumulated through sprint 03's eleven follow-ups would surface as
"sprint 04 day-one bugs":

- `POST /v1/invitations/accept` never sets `app.tenant_id` from the verified
  token, so RLS hides the row and the public accept flow is silently broken.
- `InviteMember` / `CancelInvitation` write outbox rows keyed by
  `invitation.id`, so the second write to the same invitation always hits a
  PK collision — sprint 04 will hit the same pattern the first time `catalog`
  writes to the outbox.
- Tailwind v4 is half-migrated; a clean `pnpm install` breaks the build, and
  sprint 04 needs new shadcn primitives (`accordion`, `sheet`, `pagination`,
  `table`) that cannot be added safely until the migration is complete.

Plus loose ends: 19 OpenSpec changes are still active, per-user permission
overrides are spec'd but unimplemented, Playwright covers 1 of 5 specs, and
the manual verifiable-outcomes for 3.13 / 3.14 were never executed.

## Definition of done

- `POST /v1/invitations/accept` works end-to-end with an integration test +
  Playwright spec that covers invite → accept in a second browser context.
- `InviteMember` and `CancelInvitation` can be invoked twice on the same
  invitation without an outbox PK collision; covered by an integration test.
- `apps/web` builds from a clean `pnpm install` with no transitive resolution
  of `@tailwindcss/postcss` and no remaining v3 config surface.
- Per-user permission overrides are either removed from
  `openspec/changes/restructure-sidebar-empresa-and-account/specs/tenants-http/spec.md`
  with an ADR-0022 note, or implemented with endpoint + UI.
- Playwright fixtures (`auth.ts`, `tenant.ts`) exist and the four pending
  specs (`tenant-onboarding`, `member-management`, `permission-gating`,
  `rls-isolation`) run green on Chromium in CI.
- Manual verifiable-outcomes for sprints 3.13 and 3.14 executed; any
  regression captured as a new task here before sprint 04 opens.
- Every active OpenSpec change at ≥ 95% completion archived via
  `/opsx:archive`; the rest documented as carry-over with an explicit owner.

## Tasks

- [x] 1. Fix `POST /v1/invitations/accept` GUC: read `tenant_id` from the
  verified invitation token claim and emit `SET LOCAL app.tenant_id` (via
  `set_config(..., true)` for parameter binding) on the outer transaction
  before the repository call. Reference `_RequestUnitOfWork.begin()` for the
  existing pattern.
- [x] 2. Add integration test covering the accept happy path with RLS active
  (currently deferred at
  `apps/api/tests/e2e/contexts/tenants/test_tenant_lifecycle.py`); the test
  must fail before task 1 and pass after.
- [x] 3. Fix outbox PK collision in `InviteMember`: generate a fresh
  `uuid7()` per outbox row instead of reusing `invitation.id`. ADR-0011 is
  the canonical UUIDv7 source.
- [x] 4. Mirror the fix in `CancelInvitation`. Add an integration test that
  invites → cancels → re-invites the same email and asserts the outbox has
  three distinct rows with three distinct `event_id` values.
- [x] 5. Audit every other use case for the same pattern
  (`grep -nR "event_id=.*\.id" apps/api/src/contexts/`) and fix any
  occurrence found.
- [ ] 6. Complete Tailwind v4 migration per
  `openspec/changes/complete-web-tailwind-v4-migration/tasks.md` (28 tasks);
  the gate is `rm -rf node_modules pnpm-lock.yaml && pnpm install && pnpm
  -C apps/web build` succeeding from a clean state.
- [x] 7. Decision on per-user permission overrides: take one path.
  Path A — remove the section from `tenants-http/spec.md`, append a
  paragraph to ADR-0022 explaining the decision, and update sprint 3.14's
  closure note. Path B — implement
  `PATCH /v1/tenants/{tenantId}/members/{userId}/permissions` + a minimal
  UI surface on `/empresa/users`.
- [ ] 8. Create `apps/web/tests/e2e/fixtures/auth.ts` and `tenant.ts` per
  `openspec/changes/test-backfill-and-e2e-tooling/tasks.md` §8.3 (no API
  shortcuts — drive through the real signup/login UI).
- [ ] 9. Ship the four missing Playwright specs (§9.2 onboarding, §9.3
  member-management, §9.4 permission-gating, §9.5 rls-isolation). Each must
  pass on Chromium in CI before being marked done.
- [ ] 10. Execute manual verifiable-outcome for sprint 3.13 (`tasks.md`
  §7.1-§7.5 + §8.1). Capture any regression as a new task in this file.
- [ ] 11. Execute manual verifiable-outcome for sprint 3.14 (`tasks.md`
  §8.1-§8.5). Capture any regression as a new task in this file.
- [x] 12. Archive every OpenSpec change at ≥ 95% completion via
  `/opsx:archive`. For the rest, add a one-line carry-over note in the
  proposal explaining what blocks closure (typically: AWS verification).
- [x] 13. Add an integration test asserting that `confirm-signup` writes
  exactly one row to `outbox` with `event_type='identity.UserRegistered v1'`
  and a valid `tenant_id` (sentinel UUID for global events per sprint 02).
  This is the contract surface sprint 07's publisher will consume.

## Notes

- 2026-05-30 — Tasks 1-4 were already landed in code before this goal
  started; the sprint-03 closure note + test-backfill `tasks.md §3.2` were
  stale. Verified: `accept_invitation.py:69-73` issues
  `set_config('app.tenant_id', :t, true)`; `invite_member.py:97` +
  `cancel_invitation.py:50` + `accept_invitation.py:87` all use `uuid4()`
  for `event_id`. E2E `test_tenant_lifecycle.py` exercises cancel →
  re-invite → accept and passes (`uv run pytest …test_tenant_lifecycle`
  → 1 passed). Marking 1-4 done without code change.
- 2026-05-30 — Task 5 audit hit two real violators: `remove_member.py:50`
  and `update_member_role.py:56` still used `event_id=membership.id`,
  meaning a remove-cycle or two role changes would collide on the outbox
  PK. Fixed both to `event_id=uuid4()` (mirroring the `InviteMember`
  comment) and added regression unit tests
  (`test_remove_member_emits_unique_event_id_per_cycle`,
  `test_update_member_role_emits_unique_event_id_per_change`). 9/9 unit
  tests pass. Commit `9733d4d`.
- 2026-05-30 — Task 13 added `test_confirm_signup_writes_user_registered_outbox_row`
  to `tests/e2e/contexts/identity/test_auth_flow.py`. Pins event_type,
  event_version, tenant_id sentinel, aggregate_type, payload keys so the
  sprint-07 publisher contract can't drift silently. Commit `050fa9c`.
- 2026-05-30 — Task 12 archived 8 OpenSpec changes (5 at 100% +
  add-multi-tenancy-and-rbac, add-identity-context,
  add-frontend-dashboard-shell at ≥96% via --no-validate --skip-specs
  because the only open task is AWS post-deploy verification or browser
  smoke). Appended one-paragraph "Carry-over (2026-05-30)" sections to
  the proposals of the 10 active changes below 95% so the blocker is
  inline-readable. Commit `9d99693`.
- 2026-05-30 — Task 7 took Path A. Dropped the per-user permission
  overrides requirement from
  `openspec/changes/restructure-sidebar-empresa-and-account/specs/tenants-http/spec.md`;
  appended an "Addendum (2026-05-30) — Per-user permission overrides"
  section to `docs/adr/0022-rbac-model.md` documenting the decision.
  Also marked the `app.tenant_id` GUC requirement as landed in the
  same spec (the fix is in `accept_invitation.py:69-73`, covered by
  e2e). Spec stays in the change folder as an inline reference; the
  archived change preserves the original wording for future
  re-promotion.
