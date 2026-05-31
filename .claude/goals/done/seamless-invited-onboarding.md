# Seamless invited-user onboarding

## Why

The pilot run captured a five-step ramp with one forced credential
re-entry (`/login` after `/confirm`) and one empresa-picker detour
(`/tenants` after `/invitations/accept` returns `403` for tenant-scoped
reads). Both detours are redundant — at the point each endpoint runs
the backend already has every input it needs to finish the session
state. The user explicitly flagged the re-login step as "estúpido".

Closing this collapses the ramp to three steps for the
invited-new-user path: register → confirm-with-password → accept.

## Definition of done

- ADR-0035 + sprint 3.15 follow-up + OpenSpec change merged under
  `openspec/changes/onboarding-endpoints-return-session/` and
  `openspec validate` green.
- `POST /v1/auth/confirm-signup` accepts optional `password` and
  returns a token bundle when present; `204` shape preserved when
  absent.
- `POST /v1/invitations/accept` accepts optional `refresh_token`,
  rotates the session for first-membership invitees only, returns
  `tokens: null` for veteran callers.
- SPA wires password hand-off via in-memory module store, auto-stores
  tokens after confirm and accept, no forced `/login` and no picker
  detour for first-membership invitees.
- Backend unit + integration tests green; FE unit + integration tests
  for changed paths green; three E2E specs ready
  (`invitation-accept.spec.ts` re-baselined, plus veteran +
  refresh-fallback specs).

## Tasks

- [x] 1. Author ADR-0035 + index it in `docs/adr/README.md`.
- [x] 2. Add sprint 3.15 follow-up to `docs/sprints/03-tenants-and-rls.md`
       and post-sprint extensions pointer in
       `docs/sprints/02-identity-and-rbac.md`.
- [x] 3. Create OpenSpec change `onboarding-endpoints-return-session/`
       with proposal, tasks (25 items), and three spec deltas
       (`identity-http`, `tenants-http`, `auth-frontend`).
- [x] 4. Backend: extend `ConfirmSignupRequest` + `ConfirmSignup` use
       case + identity router with optional password + 200/204
       branching; add unit + integration tests.
- [x] 5. Backend: extend `AcceptInvitationCommand` /
       `AcceptInvitationResult` / use case / dependencies / router
       with `prior_active_tenant` + `refresh_token` + optional
       `tokens`; add unit + integration tests.
- [x] 6. Frontend: in-memory password hand-off module, `signup.tsx`
       stash, `confirm.tsx` consume + delegate to route guard,
       `useConfirmSignupMutation` auto-storeTokens.
- [x] 7. Frontend: `acceptInvitation(token, refresh_token?)` client,
       `accept.tsx` snapshot refresh token + auto-storeTokens when
       response carries them; regenerated `schema.d.ts`.
- [x] 8. Tests: update FE integration mocks for new endpoint shape;
       rewrite `invitation-accept.spec.ts` E2E to the seamless flow;
       add `invitation-accept-veteran.spec.ts` and
       `signup-confirm-refresh-fallback.spec.ts`; update
       `signupConfirmLogin` fixture to skip `/login`.

## Notes

- ADR: `docs/adr/0035-onboarding-endpoints-return-session.md`.
- OpenSpec: `openspec/changes/onboarding-endpoints-return-session/`
  (validate ✓).
- Backend: 295/295 pytest green; ruff + mypy --strict + lint-imports
  ✓. Tenants context now depends on `identity.application.ports.outbound.Identity`
  (cross-context port import; allowed by the contracts).
- Frontend: typecheck + lint clean; 55 tests pass on the
  signup/confirm/invitation-accept files I touched. Five
  pre-existing failures under `tests/integration/routes/empresa/users.spec.tsx`
  trace to the user's parallel work on the empresa users route, not
  this goal.
- E2E: not executed in this session (requires Mailpit + DB + dev
  server + Playwright); specs are ready for the next `pnpm e2e --grep
  "invitation|signup-confirm"` run.
- Working tree at close: 41 entries (8 new, 33 modified) — includes
  parallel uncommitted work on `optimize-users-table-filters` that
  this goal did not touch (`user_repository.py`, `empresa/users.tsx`,
  `MembersTable.tsx`, migration `0005`, etc.).
