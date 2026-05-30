## Why

After sprints 3.7 / 3.8 / 3.9 / 3.10 polished `/tenants/new`,
two product decisions surfaced from the operator's hands-on
testing that supersede sprint 3.6's earlier plan:

1. The product term **"Organización"** that sprint 3.6 was
   about to roll out reads as corporate / foreign jargon for
   the Nicaraguan SME audience. The natural word in
   Nicaragua is **"empresa"** — shorter, better understood,
   and matching every peer accounting product the operator
   has used (Mónica, ContaSimple).
2. The tenant-creation wizard still requires 8 fiscal fields
   (RUC + régimen + municipio + DGI número + 2 dates +
   dirección + retenedor) before the user can reach the
   dashboard. For an SME owner this is too much friction at
   onboarding; many will not have the DGI papers in front of
   them on first signup. The operator's explicit ask: only
   `name` is required at creation; everything else is
   optional and fillable later.

The DB schema already supports this: migration
`0003_tenants_and_rbac.py` made every fiscal column on
`tenants` `nullable=True`. The blockers were the Pydantic
schema, the `Tenant` domain aggregate, and the repository's
`_load`. All three are addressed here.

Both decisions are captured by
[ADR-0034](../../../docs/adr/0034-empresa-product-term-and-soft-creation.md),
which supersedes the product-term portion of
[ADR-0032](../../../docs/adr/0032-tenant-vs-organization-naming.md).

## What Changes

### Backend (soft-creation)

- `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`:
  - `CreateTenantRequest`: every field except `name` becomes
    `Optional[...] = None` (`is_withholder` keeps its
    existing `default=False`).
  - `TenantResponse`: mirror the optional shape so callers
    see `None` where the tenant is fiscally incomplete.
- `apps/api/src/contexts/tenants/domain/tenant.py`:
  - `Tenant` aggregate constructor and `register` factory
    accept `ruc: Ruc | None`, `regime: Regime | None`,
    `municipality: Municipality | None`,
    `authorization_dgi: AuthorizationDgi | None`,
    `fiscal_address: str | None`.
  - `Tenant.ruc`, `.regime`, etc. accessors return the
    same `Optional[...]` shape.
- `apps/api/src/contexts/tenants/application/use_cases/create_tenant.py`:
  - `CreateTenantCommand` mirrors the optional fields.
  - The use case parses `Ruc.parse(command.ruc)` only when
    `command.ruc is not None`, and likewise for the other
    VOs.
- `apps/api/src/contexts/tenants/adapters/outbound/persistence/sqlalchemy/tenant_repository.py`:
  - `_load` constructs each VO conditionally (e.g., `Ruc(row["ruc"]) if row["ruc"] is not None else None`).
  - `add` and `update` pass `None` instead of trying to call
    `.value` on a None VO.
- `apps/api/src/contexts/tenants/adapters/inbound/http/router.py`:
  - `create_tenant` and the response mapper handle Optional
    fields.
- The `Ruc` uniqueness constraint (`uq_tenants_ruc`)
  continues to apply; Postgres treats multiple NULLs as
  distinct so multiple fiscally-incomplete tenants are
  allowed.
- Value objects (`Ruc`, `Regime`, `Municipality`,
  `AuthorizationDgi`) themselves stay **strict**: they only
  validate when constructed, which now only happens when the
  caller has a non-None value.

### Backend (tests)

- Existing tests that build full `Tenant` aggregates with
  all fields keep passing (full data is still valid).
- New tests cover: creation with only `name`; round-trip
  through the repo with NULL fiscal columns; 201 response
  shape on the HTTP boundary with all Optional fields.

### Frontend (rebrand)

- Every visible string in `apps/web/src/**/*.{tsx,ts}` that
  reads "organización" / "Organización" / "organizaciones" /
  "Organizaciones" is replaced with "empresa" / "Empresa" /
  "empresas" / "Empresas". Backend identifiers (`tenant_id`,
  `Tenant`, `/v1/tenants`, file paths under
  `features/tenants/`) stay unchanged.
- Document titles (`useDocumentTitle("Tus organizaciones")`
  → `"Tus empresas"`, `"Crear organización"` → `"Crear
  empresa"`, etc.) follow the same rule.
- Comment text in route files that referenced
  "organization" / "organización" is updated for grep
  hygiene; backend-domain comments (`Tenant`, `tenants`) are
  not changed.

### Frontend (single-step wizard)

- `apps/web/src/routes/tenants/new.tsx`: the four-step
  wizard collapses into a **single step** that asks only
  for the empresa name. The submit button reads "Crear
  empresa". On success, the SPA POSTs `{ name }` to
  `/v1/tenants`, switches into the new tenant, and lands
  on `/dashboard`.
- `apps/web/src/features/tenants/schemas/index.ts`:
  `createTenantSchema` is refactored so every field except
  `name` becomes `.optional()` and the Zod regexes are
  applied only when the value is provided.
- The Revisión panel, the per-step gating, the Tooltips,
  the DatePicker, the Selects, and the Checkbox added by
  sprints 3.7–3.10 are **removed** from `/tenants/new`
  itself but the primitives stay installed in
  `components/ui/` for the future "Editar empresa" route.

### Frontend (post-creation banner)

- `apps/web/src/routes/dashboard.tsx` (or the AppShell
  consumer that already reads the active tenant) renders an
  `<Alert>` banner when the active tenant's `ruc` or
  `fiscal_address` is `null`: "Completa los datos fiscales
  de tu empresa para emitir facturas". The link target is
  a placeholder `/empresa/editar` that points to a
  stub route reading "Próximamente" — the real edit
  experience is out of scope for this change and deferred
  to a future sprint.

### Sprint 3.6 in-flight pivot

- `openspec/changes/welcome-onboarding-rename-members/`
  proposal, tasks, and inline copy pivot every "organization"
  / "organización" string to "empresa". The capability
  `organizations-frontend` is renamed to `empresas-frontend`
  in the change's specs/ directory. The route paths
  `/organizations` / `/organizations/new` are renamed to
  `/empresas` / `/empresas/new` for sprint 3.6's eventual
  rewrite. The carry-over task lists this rebrand so the
  rewrite preserves the "empresa" copy.

## Capabilities

### New Capabilities

<!-- None. The product-term swap and the optional-fields
     relaxation are deltas on existing capabilities. -->

### Modified Capabilities

- `tenants-http`: `CreateTenantRequest` and `TenantResponse`
  drop required-ness on every field except `name`. The
  201 response is now `Optional[...]` everywhere fiscal.
- `tenants-domain`: `Tenant` aggregate and its `register`
  factory accept Optional VOs. The value objects themselves
  stay strict.
- `tenants-application`: `CreateTenantCommand` and the
  `CreateTenant` use case accept Optional fields.
- `tenants-new-form`: the wizard contract collapses to a
  single-step "Empresa" form requiring only `name`. Every
  previous requirement on Régimen / Municipio / DGI /
  Dirección stays specified but moves out of `/tenants/new`
  scope (deferred to the future "Editar empresa" route).

## Impact

- Affected code:
  - `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`
  - `apps/api/src/contexts/tenants/adapters/inbound/http/router.py`
  - `apps/api/src/contexts/tenants/domain/tenant.py`
  - `apps/api/src/contexts/tenants/application/use_cases/create_tenant.py`
  - `apps/api/src/contexts/tenants/adapters/outbound/persistence/sqlalchemy/tenant_repository.py`
  - `apps/web/src/api/schema.d.ts` (regenerated)
  - `apps/web/src/features/tenants/schemas/index.ts`
  - `apps/web/src/routes/tenants/new.tsx` (heavy rewrite)
  - `apps/web/src/routes/tenants/index.tsx` (rebrand)
  - `apps/web/src/routes/onboarding.tsx` (rebrand)
  - `apps/web/src/routes/account.tsx` (rebrand)
  - `apps/web/src/components/app-sidebar/tenant-switcher.tsx` (rebrand)
  - `apps/web/src/routes/dashboard.tsx` (incomplete-fiscal banner)
- Affected tests:
  - `apps/api/tests/unit/contexts/tenants/**` — new tests
    for optional-only creation
  - `apps/api/tests/integration/contexts/tenants/test_tenant_repository.py`
    — round-trip NULLs
  - `apps/web/tests/unit/routes/tenants-new.test.tsx` —
    rewrite for single-step wizard
- Affected docs:
  - `docs/sprints/03-tenants-and-rls.md` — append a
    "Sprint follow-up — Empresa rebrand + soft-creation
    (sprint 3.11, 2026-05-28)" section.
  - `docs/adr/0034-empresa-product-term-and-soft-creation.md`
    — already merged with this proposal.
  - `docs/adr/0032-tenant-vs-organization-naming.md` — status
    updated to "Superseded (product-term portion) by
    ADR-0034".
- Affected OpenSpec changes (in-flight):
  - `openspec/changes/welcome-onboarding-rename-members/`
    — proposal + tasks + specs pivot from "organización" to
    "empresa".
- No new ADR beyond 0034.
