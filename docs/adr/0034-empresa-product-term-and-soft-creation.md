# ADR-0034 — "Empresa" as the product term + soft-creation

**Status**: Accepted
**Date**: 2026-05-28
**Supersedes** (product-term portion): [ADR-0032](0032-tenant-vs-organization-naming.md)

## Context
[ADR-0032](0032-tenant-vs-organization-naming.md) ratified a
**tenant** (infra/backend) vs. **organization** / **organización**
(product surface) split: every visible string in the SPA was to
read "organización". Implementation of that rename was scoped into
the still-pending sprint 3.6 change
`welcome-onboarding-rename-members` and has not shipped.

Hands-on operator testing on the partially-implemented
`/tenants/new` wizard surfaced two product decisions that
override the original 3.6 plan:

1. **"Organización" reads as foreign / corporate jargon for the
   Nicaraguan SME audience this product targets.** Local SMBs
   refer to their business as **"mi empresa"** — never "mi
   organización". The word is shorter (7 vs. 12 chars), better
   understood, and matches every other Nicaraguan accounting
   product the operator has used (Mónica, ContaSimple,
   Profit Plus). The single-word "empresa" also fits sidebar
   chips and onboarding CTAs without truncation.
2. **The tenant-creation wizard requires too much fiscal data
   up front.** The current contract demands `ruc`, `regime`,
   `municipality`, `authorization_dgi.{number,valid_from,valid_to}`,
   `fiscal_address`, and `is_withholder` *before* the user can
   even reach the dashboard. For a Nicaraguan SME owner this is
   roughly 8 fields they need to copy from physical DGI papers
   they may not have in front of them when they first sign up.
   Forcing this at onboarding is a known dropout cliff. The
   operator's explicit ask: **"only the name should be required
   at creation; everything else is optional and fillable
   later"**.

Both decisions are surfaceable now because (a) the
"organización" rename has not yet executed — the existing copy
still says "organization" in places that are not committed — so
pivoting the product term is cheap, and (b) the backend already
made every fiscal column on the `tenants` table **nullable** in
migration `0003_tenants_and_rbac.py`. No new migration is
required.

## Decision
**Two product-side changes, no backend domain rename.**

### 1. Product term: "Empresa" replaces "Organización"

- Every visible string in the SPA — labels, page titles, button
  text, placeholders, alerts, sidebar chip, tooltip copy — uses
  **"empresa"** (singular) and **"empresas"** (plural), never
  "organización" / "organizaciones".
- Capitalisation follows Spanish sentence case
  (`Crear empresa`, `Tus empresas`, `Empresa activa`).
- The infra / backend split established by
  [ADR-0032](0032-tenant-vs-organization-naming.md) **stays**:
  HTTP routes (`/v1/tenants/*`), JSON keys (`tenant_id`,
  `active_tenant`), the bounded-context directory
  (`apps/api/src/contexts/tenants/`), the Postgres GUC
  (`app.tenant_id`), the Cognito attribute, table names, and
  the domain types (`Tenant`, `Membership`) all keep "tenant".
- The frontend slice directory may stay as
  `apps/web/src/features/tenants/`. Renaming the directory is
  cosmetic and out of scope; the slice keeps its name so the
  rebrand stays in copy and not in code paths.
- The earlier plan to introduce a `Tenant`→`Organization`
  adapter in the frontend (per
  [ADR-0032](0032-tenant-vs-organization-naming.md)) is
  **dropped**. The SPA reads the backend `Tenant*` shapes and
  renders them with "Empresa" labels at the call site; no
  vocabulary-translation layer is needed.

### 2. Tenant creation requires only `name`

- `POST /v1/tenants` accepts a body whose only required field
  is `name`. Every other field on `CreateTenantRequest`
  (`ruc`, `regime`, `municipality`, `authorization_dgi`,
  `fiscal_address`, `is_withholder`) is optional with default
  `None` (the existing `is_withholder` default of `False`
  stays).
- The `Tenant` domain aggregate accepts `Ruc | None`,
  `Regime | None`, `Municipality | None`, `AuthorizationDgi |
  None`, `fiscal_address: str | None`. The value objects
  themselves stay strict — they only validate when present.
- `TenantResponse` mirrors the create shape: the same fields
  are `None | <value>`. OpenAPI regen produces
  `Optional<...>` on the corresponding TypeScript types.
- The repository `_load` handles each nullable column by
  returning `None` instead of attempting to construct a VO
  from a NULL row.
- A tenant created with only `name` is considered **fiscally
  incomplete** but otherwise fully usable for non-invoicing
  features. Subsequent sprints (sales / invoicing) that
  require the fiscal data MUST gate their flows on
  completeness — that gating is *their* responsibility, not
  the creation endpoint's.
- The SPA wizard at `/tenants/new` collapses to a single step
  asking only for the empresa name. The dashboard surfaces a
  banner — "Completa los datos fiscales de tu empresa" —
  whenever the active tenant has missing fiscal fields, with
  a link to a future settings/edit screen. The edit screen
  itself is out of scope for this ADR (deferred to a follow-up
  sprint).

## Consequences

- (+) Lower friction at onboarding: the operator can land a
  newly-signed-up user on the dashboard in seconds, not after
  filling 8 fields from DGI papers.
- (+) Spanish copy reads naturally to the target audience —
  no more "organización" jargon.
- (+) No backend migration. The DB schema designed for
  nullable fiscal columns from day one (migration 0003) is
  finally honoured by the API contract and the domain.
- (+) No code-path renames. `Tenant`, `tenant_id`,
  `/v1/tenants/*`, `app.tenant_id`, the Cognito claim, and
  the bounded-context directory all stay byte-identical;
  reviewers and grep-based tooling work unchanged.
- (-) The product surface and the backend now use different
  words. This is the same trade-off
  [ADR-0032](0032-tenant-vs-organization-naming.md) accepted;
  this ADR only changes the *product* word from "organización"
  to "empresa". Project rule: SPA visible text says "empresa";
  backend / code says "tenant"; never mix in either
  direction.
- (-) Tenants with placeholder-shaped fields are a new state
  the rest of the codebase has to handle. Mitigation: feature
  flags / completeness checks happen at the use-case level in
  the sprint that adds the feature (e.g., invoicing).
- (-) The frontend `Tenant`→`Organization` adapter that
  [ADR-0032](0032-tenant-vs-organization-naming.md) planned is
  dropped; consumers read the API shapes directly. Acceptable:
  the adapter never shipped, and dropping it removes one
  indirection layer.
- (-) Tests across `apps/api/tests/**` that construct a
  `Tenant` with full fiscal data still pass (full data is
  still valid). New tests cover the `None`-everywhere creation
  path.

## Alternatives

- **Add a `draft` / `active` tenant status with a forced
  edit flow on first login.** Rejected: doubles the
  state-machine surface and forces a UI that the user
  explicitly didn't want. The "completeness banner" is the
  lighter, opt-in equivalent.
- **Frontend submits placeholder values** for absent fields
  (e.g., `ruc = "0000000000000X"`). Rejected: the `Ruc`
  uniqueness constraint forbids the same placeholder across
  tenants, the placeholder values pollute the DB with
  semantically-invalid data, and downstream consumers have
  no machine-readable way to tell "real" from "placeholder".
  NULLs in the DB are the obvious right answer and the
  schema already supports them.
- **Keep "organización"** as
  [ADR-0032](0032-tenant-vs-organization-naming.md) decided.
  Rejected: the operator (the product owner) explicitly
  asked for "empresa" and the audience research above
  supports it.

## References
- [ADR-0032 — Tenant vs Organization naming](0032-tenant-vs-organization-naming.md)
- Migration [`0003_tenants_and_rbac.py`](../../apps/api/alembic/versions/0003_tenants_and_rbac.py) — establishes the nullable fiscal columns this ADR finally exposes.
