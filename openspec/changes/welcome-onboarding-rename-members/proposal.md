> **Pivot note (2026-05-28):** Per
> [ADR-0034](../../../docs/adr/0034-empresa-product-term-and-soft-creation.md),
> the product term used by this sprint is **"empresa"**, not
> "organización". The capability `organizations-frontend`
> proposed below is renamed to `empresas-frontend`; the route
> paths `/organizations` / `/organizations/new` become
> `/empresas` / `/empresas/new`; every visible string that this
> proposal lists as "organización" reads "empresa" when the
> sprint actually implements. Backend infra (`/v1/tenants`,
> `tenant_id`, `Tenant`) keeps "tenant" per
> [ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md)
> (still authoritative for the infra/product split).
> Additionally, the create-tenant contract has been relaxed so
> only `name` is required at creation — sprint 3.6's wizard
> must collapse accordingly. See task 12 for the carry-over.

## Why

After sprint 03 closed and sprint 3.5 laid a backend + frontend
test safety net, the product flow exposes four loose ends that the
user surfaced during sprint planning:

1. The SPA navigates straight to `/dashboard` after login without
   verifying an active tenant exists. A user with zero
   memberships gets a usable shell that the backend will refuse
   on every request.
2. The `users` table forces `display_name=''`, `locale='es-NI'`,
   and `timezone='America/Managua'` as `NOT NULL` defaults — the
   product silently treats every new user as Nicaraguan-Spanish
   without ever asking. The user explicitly flagged this as
   incorrect for timezone and date handling.
3. The word "tenant" leaks into every user-facing screen even
   though peer products (Supabase, Vercel, Linear, Anthropic) all
   use "organization" / "organización" for the same concept.
4. Invitation deep links carry the signed token in the URL path,
   so the token shows up in CloudFront access logs, `Referer`
   headers, and browser history — leak surfaces a sprint-04 user
   pilot cannot accept.

Sprint 03 also accumulated two smaller debts: there is no UI for
`members:update-role` (the permission and the backend endpoint
both exist but no `<select>` is wired), and the only way to
accept an invitation is through the deep link — pasting the code
manually is not supported.

This change ships sprint 3.6 — Welcome / Onboarding / Rename /
Members — gated behind the sprint 3.5 test backfill so each new
behaviour lands with coverage on day one.

References:
[`docs/sprints/03-tenants-and-rls.md` — Sprint follow-up — Welcome / Onboarding / Rename / Members](../../../docs/sprints/03-tenants-and-rls.md#sprint-follow-up--welcome--onboarding--rename--members-sprint-36-2026-05-27),
[ADR-0031](../../../docs/adr/0031-invitation-token-transport.md),
[ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md),
[ADR-0033](../../../docs/adr/0033-deferred-locale-modeling.md).

## What Changes

### Welcome flow

- New authenticated route `/welcome` outside the AppShell, asking
  for `display_name` and `timezone` (pre-populated from
  `Intl.DateTimeFormat().resolvedOptions().timeZone`).
- The frontend guard redirects any authenticated route except
  `/welcome`, `/account` and `/health` to `/welcome` when
  `me.display_name === null`.
- `locale` is **not** rendered by the SPA — deferred per
  [ADR-0033](../../../docs/adr/0033-deferred-locale-modeling.md).

### Identity backend — nullable profile fields

- Migration 0004 drops `NOT NULL` and the `'es-NI'` /
  `'America/Managua'` / `''` server defaults from the
  `users.display_name`, `users.locale`, and `users.timezone`
  columns.
- The `User` aggregate, the SQLAlchemy mapping, the
  `UpdateProfile` use case, and the OpenAPI response schema for
  `/v1/me` are updated to expose the three fields as nullable.

### Post-login organization picker

- The post-login flow lands the user on `/organizations` (renamed
  from `/tenants`) regardless of how many memberships they have.
- The picker is shown every session; in-session switches go
  through the sidebar `OrganizationSwitcher`, never via
  `/organizations`.
- A user with zero memberships goes to `/onboarding`, which
  branches into the four-step wizard or the
  paste-your-invitation-code screen.

### Four-step organization creation wizard

- `/onboarding/new` and `/organizations/new` route to the same
  wizard: Identidad (`name`, `ruc`) → Régimen
  (`regime`, `municipality`, `is_withholder`) → Autorización DGI
  (`number`, `valid_until`) → Dirección fiscal + review.
- The wizard posts to the existing `POST /v1/tenants`, then to
  `POST /v1/tenants/{id}/switch`, then navigates to `/dashboard`.
- The old `routes/tenants/new.tsx` is removed.

### Invitation token transport

- `POST /v1/invitations/{token}/accept` is replaced by
  `POST /v1/invitations/accept` with the token in the request
  body.
- `GET /v1/invitations/{token}/preview` (new, rate-limited)
  returns `{ email, organization_name, role }` for the
  pre-signup screen.
- `_DEFAULT_INVITE_URL_TEMPLATE` becomes
  `https://<host>/invitations/accept#t={token}`; the SPA reads
  the fragment, strips it via `history.replaceState`, and POSTs
  the token in the body.
- The legacy path returns `410 Gone`.

### "Tenant" → "Organization" rename (frontend only)

- `apps/web/src/features/tenants/` → `features/organizations/`.
- `TenantSwitcher` → `OrganizationSwitcher`.
- Routes: `/tenants` → `/organizations`,
  `/tenants/$tenantId/members` →
  `/organizations/$organizationId/members`.
- Sidebar nav label, page titles, and all visible copy use
  "Organization" / "Organización".
- Backend names (`/v1/tenants/*`, `tenant_id`, `app.tenant_id`,
  `custom:active_tenant`, `contexts/tenants/`) are
  **unchanged** per [ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md).

### Member role-change UI

- `routes/organizations/$organizationId/members.tsx` adds an
  inline `<select>` per non-owner member, gated by
  `useHasPermission("members:update-role")`, wired to
  `PATCH /v1/tenants/{id}/members/{user_id}`.

### Manual invitation acceptance

- New route `/invitations/accept` (no token in path) with a paste
  input that POSTs the token via the new endpoint.

## Impact

- Affected specs:
  - `welcome-flow` (new)
  - `organizations-frontend` (new — covers the rename, picker,
    wizard, member admin and manual invitation acceptance)
  - `identity-domain` (modified — nullable profile fields)
  - `identity-http` (modified — nullable shape on `/v1/me`)
  - `database-schema-bootstrap` (modified — migration 0004)
  - `tenants-http` (modified — invitation endpoint contract +
    preview + 410 on legacy path)
- Affected code:
  - `apps/api/alembic/versions/0004_drop_user_profile_defaults.py`
  - `apps/api/src/contexts/identity/domain/user.py`
  - `apps/api/src/contexts/identity/adapters/outbound/persistence/sqlalchemy/user_repository.py`
  - `apps/api/src/contexts/identity/adapters/inbound/http/{schemas,router}.py`
  - `apps/api/src/contexts/tenants/adapters/inbound/http/{router,schemas,dependencies}.py`
  - `apps/web/src/features/organizations/**` (renamed slice)
  - `apps/web/src/routes/{welcome,organizations,onboarding,invitations}/**`
  - `apps/web/src/components/app-sidebar/organization-switcher.tsx`
  - `apps/web/src/lib/route-guard.ts`
- Affected docs: the sprint 3.6 follow-up section in
  [`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md);
  three new ADRs (0031, 0032, 0033) already merged alongside
  this proposal.

## Out of scope

- No backend rename. The hexagonal context, the GUC, the JWT
  claim, the routes, and every table name keep "tenant".
- No i18n implementation. Spanish is the only locale; ADR-0033
  documents the deferral.
- No new bounded context. All backend changes live in the
  `identity` and `tenants` contexts already shipped.
- No member-bulk-invite / CSV-import flow.
