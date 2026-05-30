# ADR-0032 — "Tenant" in infra, "Organization" in product

**Status**: Accepted (infra/product split) · **Superseded** for the product term by [ADR-0034](0034-empresa-product-term-and-soft-creation.md) — the product surface uses **"Empresa"**, not "Organización".
**Date**: 2026-05-27

## Context
Sprint 03 introduced the `tenants` bounded context, the
`tenant_members` table, the `app.tenant_id` Postgres GUC, the
`custom:active_tenant` Cognito attribute, and `/v1/tenants/*` HTTP
routes. The word "tenant" is now woven through migrations, RLS
policies, JWT claims, repository names, route handlers, and the
hexagonal directory structure under
`apps/api/src/contexts/tenants/`.

User-facing product copy and the frontend slice followed the same
naming by default. Sprint 3.6 challenges that: the product surface
should say "organización" / "organization" because (a) end users
read "tenant" as a technical term they don't recognise, (b)
Supabase, Vercel, Anthropic, Linear and most peer products call
the same concept "organization" or "workspace", and (c) the
fiscal entity backing a `Tenant` in this product really is an
organization in the regular meaning of the word — a registered
business with employees, an RUC, and an address.

Renaming everything is tempting but expensive: ~250 references to
`tenant` across backend code, tests, migrations, RLS policies and
seed data; the GUC is part of every RLS check; the JWT claim is
emitted by Cognito under `custom:active_tenant`; downstream docs
([ADR-0002](0002-postgres-rls.md),
[ADR-0022](0022-rbac-model.md),
[`docs/05-multi-tenancy.md`](../05-multi-tenancy.md)) all use the
word. A flag-day rename also breaks every consumer of the OpenAPI
schema generated from those endpoints.

## Decision
**Split the vocabulary on the product/infra boundary.**

- **Infra and backend domain** keep the word **"tenant"**: HTTP
  routes (`/v1/tenants/*`), JSON payload keys (`tenant_id`,
  `active_tenant`), the bounded-context directory
  (`apps/api/src/contexts/tenants/`), the Postgres GUC
  (`app.tenant_id`), the RLS column (`tenant_id`), the Cognito
  attribute (`custom:active_tenant`), table names
  (`tenant_members`), domain types (`Tenant`, `Membership`,
  `Invitation`), and all migrations.
- **Product surface** uses **"organization"** /
  **"organización"**: every visible string in the SPA, the
  frontend slice (`apps/web/src/features/organizations/`),
  frontend route paths (`/organizations`,
  `/organizations/$organizationId/members`,
  `/onboarding/new`), frontend TypeScript types
  (`Organization`, `OrganizationMembership`,
  `OrganizationInvitation`), and any user-readable error message.
- The boundary lives in `apps/web/src/features/organizations/api/`,
  which holds a thin adapter that maps the backend `Tenant*`
  shapes (still emitted by the OpenAPI schema) to the frontend
  `Organization*` types. The adapter is the only place that knows
  both vocabularies.

## Consequences
- (+) Users see consistent product language; no leaking technical
  jargon in the UI.
- (+) Backend evolution is unblocked: migrations, RLS, JWT and
  schemas keep their stable names. No risk of breaking the
  multi-tenant isolation invariants documented in
  [ADR-0002](0002-postgres-rls.md).
- (+) A future i18n pass can localise "organización" without
  touching backend strings.
- (-) The frontend gains a tiny translation layer. It pays for
  itself by isolating the rename to one place: if the backend
  vocabulary ever does change, the adapter is the only file that
  needs to follow.
- (-) Code reviewers need to remember the convention. The first
  CLAUDE.md addendum after this ADR documents it as a project
  rule.

## Alternatives
- **Rename everywhere (backend + frontend)** — rejected: ~250
  references to update, a destructive migration on the `users` and
  `tenant_members` tables, a JWT claim rename that breaks every
  issued token, and a hard cutover for the OpenAPI schema. All
  pain for cosmetic gain at the system boundary.
- **Keep "tenant" everywhere (including UI)** — rejected: end
  users do not recognise the word. Sprint 3.6 onboarding flow
  needs friendly product copy.
- **Use "workspace"** — rejected: in Nicaragua an "espacio de
  trabajo" sounds like a meeting room, not a registered business.
  "Organización" matches the fiscal reality of the entity
  (`ruc`, `regime`, `municipality`, `authorization_dgi`).

## Revisit triggers
- The product expands to host concepts that are clearly *not*
  organizations (personal workspaces, sandboxes). At that point
  the vocabulary may need a second dimension.
- A backend rename becomes free for an unrelated reason (e.g. a
  major migration consolidates the schema). The adapter layer
  can be retired in that case.
