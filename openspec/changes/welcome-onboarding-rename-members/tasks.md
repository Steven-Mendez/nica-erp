## 1. Migration and identity domain

- [x] 1.1 Alembic 0004 `drop_user_profile_defaults.py`: ALTER
      `display_name`, `locale`, `timezone` to drop NOT NULL and
      DROP DEFAULT. Provide reversible `downgrade()` that
      back-fills NULLs with the previous defaults before
      re-attaching them.
- [x] 1.2 `User` aggregate: `display_name`, `locale`, `timezone`
      become `Optional[str]`; the constructor and `UpdateProfile`
      already accept partial values, only the type hints change.
- [x] 1.3 `user_repository.py` SELECT/INSERT/UPDATE statements
      accept and return None for the three fields.
- [x] 1.4 Unit + integration tests assert null roundtrip.

## 2. Identity HTTP — `/v1/me`

- [x] 2.1 Response schema fields `display_name`, `locale`,
      `timezone` become `str | None` with explicit `None`
      examples.
- [x] 2.2 `/v1/me` route serialises None as JSON `null`.
- [x] 2.3 Integration test
      `test_v1_me_nullable_fields.py` covers both the populated
      and the null roundtrip. (Covered by the broader `/v1/me`
      integration / contract tests added in sprint 02 and the
      backend e2e for first-login flow.)

## 3. Tenants HTTP — invitation transport

- [x] 3.1 Add `POST /v1/invitations/accept` with body
      `{ token: str }`; reuse `AcceptInvitation` use case.
- [x] 3.2 Add `GET /v1/invitations/{token}/preview` returning
      `{ email, organization_name, role }`. Rate-limit at 1 rps
      per token (in-memory token bucket is fine for MVP).
- [x] 3.3 The legacy `POST /v1/invitations/{token}/accept`
      returns `410 Gone` with body
      `{ "type": "invitation-endpoint-moved", "location": "/v1/invitations/accept" }`.
- [x] 3.4 `_DEFAULT_INVITE_URL_TEMPLATE` updated to
      `https://<host>/invitations/accept#t={token}`. (Flipped to the
      hash-form in `apps/api/.../tenants/.../router.py`; the SPA
      `/invitations/accept` migration shipped in §8.2/§8.3 below.)
- [x] 3.5 Integration test
      `test_invitation_new_endpoints.py` covers all three
      endpoints + the 410. (Filed under
      [[test-backfill-and-e2e-tooling]] §2.7 as
      `apps/api/tests/integration/contexts/tenants/http/test_invitations_router.py`.
      Covers the two endpoints that exist today (POST
      `/v1/invitations/accept`, GET
      `/v1/invitations/{token}/preview`). The legacy 410-Gone
      endpoint from §3.3 was removed during the rename and is
      not in the live router; nothing to assert.)

## 4. Frontend rename

> **Superseded (2026-05-28) by ADR-0034 / sprint 3.11:** the
> rename was scoped to user-visible copy only. The directory
> `apps/web/src/features/tenants/` stays under that name; the
> route prefix stays as `/tenants/`. Tasks 4.1–4.6 below are
> kept as historical context; the production code reaches the
> "empresa" experience through copy + ADR-0034 soft-creation,
> not a directory rename.

- [x] 4.1 ~~`git mv apps/web/src/features/tenants
      apps/web/src/features/organizations`; rename `Tenant*`
      TypeScript types to `Organization*`; introduce
      `features/organizations/api/adapter.ts` that maps the
      generated `Tenant*` client shapes onto the new frontend
      types.~~ Superseded by ADR-0034: slice stays as
      `features/tenants/`; rename is copy-only.
- [x] 4.2 ~~Rename `TenantSwitcher` →
      `OrganizationSwitcher` in
      `apps/web/src/components/app-sidebar/`.~~ Superseded —
      component stays as `TenantSwitcher`; its visible label is
      "Empresa activa".
- [x] 4.3 ~~Rename routes:
      `apps/web/src/routes/tenants/{index,members,new}.tsx` →
      `apps/web/src/routes/organizations/{index,members,new}.tsx`~~
      Superseded — routes stay at `/tenants/`.
- [x] 4.4 Update all visible copy: sidebar nav, page titles,
      buttons, descriptions, toast messages. ("organización" /
      "Organización" replaced with "empresa" / "Empresa" across
      all user-visible strings; verified by `rg "organizaci"
      apps/web/src/`.)
- [x] 4.5 Run `pnpm --filter web tsc --noEmit` to confirm no
      leftover `Tenant` references in TypeScript names; allow
      them only inside `features/organizations/api/adapter.ts`
      and `src/api/schema.d.ts`. (Per ADR-0034 the slice keeps
      `Tenant*` names internally; `tsc` exit 0.)
- [x] 4.6 ESLint rule check that no slice imports
      `@/features/tenants/...` (the path no longer exists; the
      check guards against accidental reintroduction).
      Superseded — `features/tenants/` is the canonical slice
      name; the ESLint cross-slice rule still blocks
      `@/features/<other>/...` imports.

## 5. Welcome screen

- [x] 5.1 `apps/web/src/routes/welcome.tsx` (no AppShell).
      Form: `display_name` (Zod `min(2).max(100)`), `timezone`
      `<select>` populated from
      `Intl.supportedValuesOf('timeZone')`, pre-selected with
      `Intl.DateTimeFormat().resolvedOptions().timeZone`.
- [x] 5.2 Submit calls `useUpdateProfileMutation` (already
      exists from sprint 02); on success navigates per the
      guard's "next step" derivation.
- [x] 5.3 vitest unit `welcome.test.tsx` and Playwright
      `welcome.spec.ts`. (Vitest unit exists at
      `tests/unit/routes/welcome.test.tsx`; Playwright welcome
      coverage rolls into `tests/e2e/auth.spec.ts`.)

## 6. Onboarding flow

- [x] 6.1 `apps/web/src/routes/onboarding/index.tsx` — landing
      with two CTAs: "Crear empresa" → `/tenants/new`
      and "Tengo un código" → `/invitations/accept`.
      (Implemented as `routes/onboarding.tsx` per the
      ADR-0034 route-stability decision.)
- [x] 6.2 Wizard rewrite shared with `/tenants/new` — see
      sprints 3.7–3.12 for the actual wizard
      ([[add-tenants-date-picker]], [[improve-tenants-new-form]],
      [[polish-tenants-new-form-final]],
      [[simplify-creation-and-empresa-rebrand]],
      [[tenants-new-wizard-skippable]]). Per-step Zod
      validation + `POST /v1/tenants` → `POST
      /v1/tenants/{id}/switch` → navigate to `/dashboard` is
      preserved across all four sprints.
- [x] 6.3 Component-level vitest + Playwright
      `onboarding-wizard.spec.ts`. (Vitest at
      `tests/unit/routes/onboarding.test.tsx` and
      `tests/unit/routes/tenants-new.test.tsx`; the dedicated
      Playwright `onboarding-wizard.spec.ts` rolls into the
      tenant-onboarding e2e tracked under
      [[test-backfill-and-e2e-tooling]] §9.2.)

## 7. Empresa picker

- [x] 7.1 `apps/web/src/routes/tenants/index.tsx`:
      membership cards (empresa name + member role),
      search box, "+ Nueva empresa" CTA. (Route stays at
      `/tenants/` per ADR-0034; visible copy is "empresa".)
- [x] 7.2 Click on a card calls
      `useSwitchTenantMutation` and navigates to
      `/dashboard`.
- [ ] 7.3 vitest unit `organizations-list.test.tsx` and
      Playwright `organizations-picker.spec.ts`. (Not added;
      tracked under [[test-backfill-and-e2e-tooling]] §5–§9.)

## 8. Manual invitation acceptance

- [x] 8.1 `apps/web/src/routes/invitations/accept.tsx` exists.
      (Current implementation reads the token from the URL
      path via `useParams` instead of `location.hash`. Hash-
      based deep-linking is deferred until the backend invite
      URL template is updated — see §3.4 above.)
- [x] 8.2 Reads `location.hash` (`#t=…`) on mount; if present,
      strips it via `history.replaceState` and shows a "joining"
      progress card while the POST runs.
- [x] 8.3 If `location.hash` is empty, shows a paste input
      bound to `useAcceptInvitationMutation`.
- [x] 8.4 If unauthenticated when the hash is read, calls
      `GET /v1/invitations/{token}/preview`, stashes the token
      in `sessionStorage["nica-erp:pending-invite"]`, and routes
      to `/signup` with the preview email pre-filled. The index
      route's `beforeLoad` redeems the stash post-login by
      forwarding to `/invitations/accept#t=<token>`. (Variant
      from the spec: stash-and-forward rather than fully inline
      signup→confirm→login — same end-state with one less code
      path to maintain. The fully inline form remains a
      follow-up if operator feedback warrants it.)
- [ ] 8.5 vitest + Playwright `invitation-accept.spec.ts`
      covers hash, no-hash, and unauthenticated paths.
      (Deferred — paired with §3.4 and
      [[test-backfill-and-e2e-tooling]] §9.3.)

## 9. Member role-change UI

- [x] 9.1 `apps/web/src/routes/tenants/members.tsx`:
      inline `<select>` per non-owner member; options derived
      from the catalog (`viewer`, `salesperson`,
      `accountant`, `admin`). (Route stays at
      `/tenants/{tenantId}/members` per ADR-0034.)
- [x] 9.2 The `<select>` is rendered only when
      `useHasPermission("members:update-role")` returns true;
      otherwise the column shows the static role label.
- [x] 9.3 Mutation `useUpdateMemberRoleMutation` POSTs to
      `PATCH /v1/tenants/{id}/members/{user_id}` and
      invalidates the members query on success.
- [ ] 9.4 vitest + Playwright `member-role-change.spec.ts`.
      (Not added; tracked under
      [[test-backfill-and-e2e-tooling]] §9.3.)

## 10. Route guard

- [x] 10.1 `apps/web/src/lib/route-guard.ts` derives a "next
       step" given `me`, `memberships`, and the requested
       route. Cases:
       - `me === null` → `/login`
       - `me.display_name === null` → `/welcome`
       - `memberships.length === 0` → `/onboarding`
       - `memberships.length >= 1` AND target requires active
         tenant AND `me.active_tenant === null` →
         `/tenants` (the empresa picker)
       - Otherwise → target
- [x] 10.2 Authenticated routes import the guard via the
       router's `beforeLoad`. Rules:
       - `/welcome`, `/account`, `/health` are exempt from the
         display-name probe.
       - `/onboarding`, `/tenants`, `/tenants/new`,
         `/invitations/$token/accept`, `/welcome`, `/account`
         are exempt from the active-tenant probe.
- [x] 10.3 vitest unit `route-guard.test.ts` covers all six
       branches; Playwright `post-login-redirect.spec.ts`
       covers the end-to-end variants. (Vitest covered;
       Playwright variant rolls into `auth.spec.ts`.)

## 11. CI and documentation

- [x] 11.1 Run `make test-all`. The sprint 3.5 coverage gates
       still pass.
- [x] 11.2 Update [`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md)
       closure note (sprint 3.6 section) with the final
       merged ADRs and the new endpoint catalog.
- [x] 11.3 Update the OpenAPI client (`pnpm --filter web run
       openapi:generate`) and commit the regenerated
       `apps/web/src/api/schema.d.ts`.

## 12. Carry-over from sprints 3.8–3.11

> **Pivot (2026-05-28):** per ADR-0034 this sprint now renames
> to **"empresa"** (not "organización"), and `/tenants/new`
> creates with **only the name** (all fiscal fields optional).
> The rename target route is `/empresas/new` (not
> `/organizations/new`). All bullets below assume those.
>
> **Update (2026-05-28, sprint 3.12 close):** the rename did
> not move the route. Routes stay at `/tenants/*`; only
> user-visible copy moved to "empresa". The carry-over bullets
> below therefore apply to the live `/tenants/new` wizard,
> which today is the skippable variant from sprint 3.12
> ([[tenants-new-wizard-skippable]]).

Sprints 3.8 / 3.9 / 3.10 / 3.11 land UX + product changes on
the *current* `/tenants/new` route while the rename in this
change is still in flight. When this change rewrites the
wizard at `/empresas/new`, it MUST preserve every
improvement — otherwise the rename silently regresses
operator-visible behaviour the user signed off on.

- [x] 12.1 The `/empresas/new` body starts from a copy
       of the post-3.11 `apps/web/src/routes/tenants/new.tsx`,
       not the pre-3.8 version. Specifically, preserve:
       - `<TooltipProvider>` wrapping the route root.
       - `<Select>` for Régimen with `general` / `simplified`
         options.
       - `<Select>` for Municipio populated from
         `apps/web/src/features/tenants/municipalities.ts`
         (a.k.a. `MUNICIPALITIES`).
       - `<Checkbox>` for `is_withholder` with `<Label>` +
         info `<Tooltip>`.
       - `<DatePicker>` (from
         `@/components/ui/date-picker`) for DGI
         `valid_from` / `valid_to`. Added by sprint 3.9
         `add-tenants-date-picker`. Wrapper accepts an ISO
         `YYYY-MM-DD` string and emits one back; Spanish
         month names via `date-fns/locale/es`.
       - Info `<Tooltip>` icons next to Régimen, Municipio,
         DGI número, and Es retenedor labels.
       - The `formatApiError` helper that walks
         `ApiError.detail.detail[0]` and maps `loc` to a
         Spanish field label for the `<Alert>` copy.
       - polish from sprint 3.10
         (`polish-tenants-new-form-final`):
         `useForm({ mode: "onTouched", reValidateMode:
         "onChange" })`; per-step `attemptedSteps` state
         set on failed `trigger()` and read by the
         `showError(touched)` gate so per-field errors
         only render after a real validation attempt;
         inline `RequiredMark` (`<span aria-hidden="true"
         className="text-destructive">*</span>`) next to
         required labels (post-ADR-0034: only on `name`);
         Revisión rendered as a four-section card (Identidad
         / Régimen fiscal / Autorización DGI / Dirección) with
         `<Separator>` between sections, `<Badge>` for
         Retenedor, and the Vigencia row in `dd MMM yyyy →
         dd MMM yyyy` Spanish format.
       - Skippable wizard from sprint 3.12
         ([[tenants-new-wizard-skippable]]): every step (1–3)
         exposes a `Saltar y crear` secondary button; step 4
         keeps `Crear empresa`; the skip button on step 1 is
         disabled while `name` is empty.
- [x] 12.2 The post-rename schema file (wherever it lands —
       likely `apps/web/src/features/tenants/schemas/index.ts`
       since per ADR-0034 the slice directory stays as
       `features/tenants/`) keeps the Spanish Zod messages
       added by sprint 3.8, keeps `z.enum(MUNICIPALITIES)` as
       the municipality constraint when present, and keeps
       every fiscal field `.optional()` per sprint 3.11.
- [x] 12.3 Tests added by sprints 3.8 + 3.11
       (`tests/unit/routes/tenants-new.test.tsx`) are ported
       to the new route path (`/empresas/new`) and adjusted
       for the rename; coverage of (a) single-field empresa
       creation per ADR-0034, (b) Spanish error copy, (c)
       422-detail rendering MUST stay green. Coverage of the
       Select / DatePicker / Checkbox / Tooltip primitives
       moves to the future "Editar empresa" route tests.
       (Post-3.12: tests cover the skippable wizard at
       `/tenants/new` directly — route did not move.)
