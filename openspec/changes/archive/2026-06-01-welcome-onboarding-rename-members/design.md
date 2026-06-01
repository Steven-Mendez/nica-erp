## Context

This change stacks on top of
[`add-multi-tenancy-and-rbac`](../add-multi-tenancy-and-rbac/proposal.md),
[`add-frontend-dashboard-shell`](../add-frontend-dashboard-shell/proposal.md),
and [`test-backfill-and-e2e-tooling`](../test-backfill-and-e2e-tooling/proposal.md).
The architectural envelope is fixed by:

- [`docs/sprints/03-tenants-and-rls.md`](../../../docs/sprints/03-tenants-and-rls.md)
  — including the sprint 3.6 follow-up section that this change
  materialises.
- [`docs/06-security-model.md`](../../../docs/06-security-model.md)
  and [ADR-0022](../../../docs/adr/0022-rbac-model.md) — the
  RBAC matrix; this change wires the missing UI for the
  `members:update-role` permission without changing the matrix.
- [`docs/09-frontend.md`](../../../docs/09-frontend.md) — the
  feature-slice rules ([`project_frontend_not_hexagonal`](file:///Users/wern/.claude/projects/-Users-wern-Documents-GitHub-nica-erp/memory/project_frontend_not_hexagonal.md),
  [`project_frontend_slice_layout`](file:///Users/wern/.claude/projects/-Users-wern-Documents-GitHub-nica-erp/memory/project_frontend_slice_layout.md))
  this change must respect during the rename.
- [ADR-0031](../../../docs/adr/0031-invitation-token-transport.md),
  [ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md),
  [ADR-0033](../../../docs/adr/0033-deferred-locale-modeling.md).

## Goals / Non-Goals

**Goals**

- A freshly signed-up user lands on `/welcome`, fills in
  `display_name` and `timezone`, and is then routed by the same
  guard logic that handles existing users.
- A user with zero memberships is offered "create" or
  "redeem invitation code" — never the dashboard.
- A user with one or more memberships always picks an
  organization at `/organizations` post-login; in-session
  switches use the sidebar.
- Invitation links never expose the token in server logs,
  `Referer` headers, or browser history.
- The visible product never says "tenant"; the codebase backend
  always does.
- An admin can change a member's role from the members page.

**Non-Goals**

- Backend rename. Out of scope and explicitly rejected in
  [ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md).
- i18n. The SPA is Spanish-only; the deferred locale modelling
  is documented in
  [ADR-0033](../../../docs/adr/0033-deferred-locale-modeling.md).
- Member bulk import, owner transfer, organization deletion. All
  are sprint 04+ topics.
- Cognito-side custom-attribute changes. The
  `custom:active_tenant` attribute stays in place.

## Decisions

### 1. First-login probe is `display_name IS NULL`

Decision: a user is considered "first login" when `me.display_name`
is `null` (after migration 0004). The SPA guard fires on this
condition; no separate `profile_completed_at` column is added.

Rationale: the welcome screen captures `display_name` first;
once it is set, the user has completed onboarding. The two
remaining fields (`timezone`, `locale`) carry their own
semantics independent of "is the profile complete?". Adding a
dedicated boolean would couple three independent things to one
flag. The null-check is cheap and obvious in both Python and
TypeScript.

Trade-off: a user who clears their display name (an unsupported
flow today) would be sent back to `/welcome`. Acceptable; the
fix is to add a UI affordance that prevents clearing, which is a
sprint 04+ concern.

### 2. Wizard is shared between onboarding and "create another"

Decision: `/onboarding/new` and `/organizations/new` resolve to
the same wizard component. The route name differs only to
preserve breadcrumbs and analytics. The wizard does not branch
on its entry route.

Rationale: the data captured is identical (the Nicaragua fiscal
metadata); the distinction is purely contextual ("first" versus
"another"). Forking the component duplicates validation, layout,
and tests for no behavioural difference.

### 3. Organization picker is always shown post-login

Decision: a user with one membership and a populated
`me.active_tenant` still passes through `/organizations` on each
fresh login. The sidebar `OrganizationSwitcher` handles
in-session switching without round-tripping.

Rationale: the user requested this explicitly during planning
(Supabase precedent). The benefit is a deterministic mental model
for which organization the session belongs to — important when
sensitive operations like invoice issuance land in sprint 04.

### 4. Frontend rename uses an adapter, backend stays put

Decision: the rename touches only `apps/web/src/`. A thin
adapter in
`apps/web/src/features/organizations/api/adapter.ts` maps
backend `Tenant*` shapes (still emitted by the OpenAPI client
in `src/api/schema.d.ts`) onto frontend `Organization*` types.
The generated client is untouched.

Rationale: per
[ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md)
the rename is product-only. Touching the generated client risks
breaking the typed contract; an adapter is the boundary.

### 5. Hash-fragment token: SPA-only carrier

Decision: the invitation email link points at
`https://<host>/invitations/accept#t={token}`. The SPA reads
`location.hash`, calls
`history.replaceState(null, '', location.pathname)`, and POSTs
the token in the body of
`/v1/invitations/accept`. The legacy path returns
`410 Gone`.

Rationale: per
[ADR-0031](../../../docs/adr/0031-invitation-token-transport.md).

Trade-off: a user with JavaScript disabled cannot accept the
invitation through the email link. Acceptable; the manual paste
screen at `/invitations/accept` (no hash) is the documented
escape hatch.

### 6. The preview endpoint trades minimal exposure for UX

Decision: `GET /v1/invitations/{token}/preview` exists so the
SPA can pre-fill the invited email when the recipient is a
brand-new user. The response is `{ email, organization_name,
role }` — all data the recipient already has from the email
body. The endpoint is rate-limited per token.

Rationale: without it, the SPA either decodes the signed token
client-side (security smell) or asks the recipient to retype
their email (UX regression). The preview is a thin,
audit-friendly affordance whose impact is bounded by the
rate-limit and the token TTL.

### 7. `locale` column kept, hidden from UI

Decision: migration 0004 makes `locale` nullable and drops the
default; the column stays in the schema; the SPA never renders
it; `/v1/me` returns `string | null`. No frontend code reads
the field.

Rationale: per
[ADR-0033](../../../docs/adr/0033-deferred-locale-modeling.md).

## Risks / Trade-offs

- **Rename touches ~150 imports.** Mitigation: the sprint 3.5
  test net is the prerequisite; the rename PR is reviewed
  against green tests, not green eyes.
- **Migration 0004 is reversible on column metadata but not on
  data**: existing rows keep their values. If a downgrade is
  ever attempted on a populated database, the default would
  re-attach but the rows that were set to `NULL` post-upgrade
  would fail the `NOT NULL` constraint. Mitigation: the
  migration's `downgrade()` re-attaches the defaults *and* sets
  the columns to their previous default for any `NULL` rows.
- **Hash-fragment requires JS-enabled clients**: documented in
  the accept screen and in
  [ADR-0031](../../../docs/adr/0031-invitation-token-transport.md).
- **Always-show picker adds one click**: the user explicitly
  accepted this during planning.

## Migration plan

1. Land sprint 3.5 (test backfill) and confirm CI is green.
2. Merge the three ADRs (0031, 0032, 0033) and the sprint 3.6
   follow-up section in the sprint doc.
3. Land the backend migration 0004 + identity domain/HTTP
   adjustments + tenants HTTP contract changes.
4. Land the frontend rename in one PR, gated by the rename
   spec's scenarios.
5. Land the welcome flow, the picker, the wizard, the role-change
   UI, and the manual invitation acceptance screen.
6. Smoke test on a deployed environment (sprint 09 will codify
   the end-to-end smoke; until then, manual verification per
   the sprint doc's *Verifiable outcome* section).

## Open Questions

- Rate-limit budget for `GET /v1/invitations/{token}/preview`:
  start at one request per second per token, revisit if
  invitation usage warrants.
- Sidebar `OrganizationSwitcher` placement: stays in the sidebar
  header as the sprint-03 dashboard-shell addendum decided.
