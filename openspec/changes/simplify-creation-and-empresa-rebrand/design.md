## Context

The current `POST /v1/tenants` requires 8 fiscal fields.
The DB schema, however, made every fiscal column nullable
back in migration 0003 (the migration was written
defensively for exactly this kind of pivot). The blockers
are:

1. Pydantic `CreateTenantRequest` and `TenantResponse`
   reject `None` for `ruc`, `regime`, `municipality`,
   `authorization_dgi`, `fiscal_address`.
2. The `Tenant` domain aggregate constructor and the
   `Tenant.register(...)` factory require all fields.
3. The repository `_load` calls `Ruc(row["ruc"])` and
   friends, blowing up on NULL.
4. The frontend Zod schema requires every field.
5. The wizard UI walks the user through every field.

`ADR-0034` documents the policy: only `name` is required,
the other fields default to `None`, and the rest of the
system honors that. The same ADR pivots the product term
from "organización" (sprint 3.6's plan, ADR-0032) to
"empresa" because the SME audience reads "empresa" as the
natural word for their business.

## Goals / Non-Goals

**Goals:**

- `POST /v1/tenants` with `{ "name": "..." }` (no other
  fields) returns 201 with a `TenantResponse` whose
  fiscal fields are `null`.
- The DB stores `NULL` in `ruc`, `regime`, `municipality`,
  `authorization_dgi_*`, `fiscal_address` when not
  provided; the row otherwise looks identical to a
  fully-populated tenant.
- The SPA wizard at `/tenants/new` shows ONE field
  (Nombre de la empresa) and one CTA (Crear empresa).
- Every user-visible string in `apps/web/src/` that read
  "organización" now reads "empresa", preserving Spanish
  sentence case.
- `apps/api/` backend code, `/v1/tenants/*` routes, the
  `Tenant` domain type, the `tenant_id` JSON key, and the
  `app.tenant_id` GUC stay byte-identical.
- The existing carry-over task in
  `welcome-onboarding-rename-members` is updated so sprint
  3.6's rewrite preserves the rebrand + soft-creation.

**Non-Goals:**

- No new "Editar empresa" UI in this change. A stub route
  is added that reads "Próximamente"; the real editor is
  deferred.
- No backend rename. `Tenant`, `Membership`,
  `/v1/tenants`, `tenant_id`, `app.tenant_id`,
  `custom:active_tenant`, the directory
  `apps/api/src/contexts/tenants/`, and table names all
  stay.
- No frontend slice rename. `apps/web/src/features/tenants/`
  stays. Per ADR-0034 the rebrand is in *copy*, not in
  code paths.
- No new Alembic migration. The DB schema is already
  prepared (migration 0003).
- No domain-level "tenant status" change. A tenant with
  NULL fiscal fields keeps `status='active'`; downstream
  flows that need RUC will gate themselves on
  `tenant.ruc is not None`.

## Decisions

### D1: Optional VOs at the aggregate boundary, strict VOs internally

**Choice:** `Tenant` accepts `Ruc | None`. The `Ruc` VO's
constructor itself still raises on a malformed string. The
gate moves from "the field exists" to "if the field exists,
it's valid".

**Rationale:** Keeps each VO single-responsibility — Ruc
*is* what a valid Nicaraguan RUC looks like, regardless of
whether a given tenant has one. The aggregate models the
business reality: a tenant in this product may not have
provided their RUC yet.

### D2: Pydantic Optional with `default=None`, not `default_factory`

**Choice:**
```python
ruc: Optional[str] = Field(default=None, examples=["0010101800010X"])
```

**Rationale:** Pydantic emits the cleanest OpenAPI for
`Optional[str] = None`: TypeScript codegen produces
`ruc?: string | null`, which is exactly what the frontend
already expects from openapi-fetch's `?` operator.
`default_factory` would emit a non-null default in the
schema, breaking the "not provided" semantics.

### D3: `is_withholder` keeps `default=False`, not Optional

**Choice:** `is_withholder: bool = Field(default=False)`
stays.

**Rationale:** A boolean's "not specified" state IS
`False`. Making it Optional adds a tri-state with no
operational meaning — every consumer either ticks the box
or doesn't.

### D4: Repository `_load` returns the same `Tenant` shape, with `None` where columns are NULL

**Choice:**
```python
return Tenant(
    id_=row["id"],
    ruc=Ruc(row["ruc"]) if row["ruc"] is not None else None,
    regime=Regime(row["regime"]) if row["regime"] else None,
    ...
)
```

**Rationale:** The Optional pattern propagates from the DB
all the way up. The use case caller can `if
tenant.ruc is not None:` instead of guarding against
empty strings. No "magic" sentinel values.

### D5: Repository `add` / `update` `INSERT` passes `None`

The bound parameters dict already supports `None` →
`NULL`; we just pass `tenant.ruc.value if tenant.ruc is
not None else None` for each column.

### D6: Frontend Zod schema relaxation

**Choice:** Rewrite `createTenantSchema` so only `name`
is required:
```ts
export const createTenantSchema = z.object({
  name: z.string().min(1, { message: "..." }).max(200, { message: "..." }),
  ruc: z.string().regex(/^\d{13}[A-Z]$/u, { message: "..." }).optional(),
  regime: z.enum(["general", "simplified"]).optional(),
  municipality: z.enum(MUNICIPALITIES, { message: "..." }).optional(),
  authorization_dgi: z.object({
    number: z.string().min(1).max(32),
    valid_from: z.string().regex(...),
    valid_to: z.string().regex(...),
  }).optional(),
  fiscal_address: z.string().min(1).max(500).optional(),
  is_withholder: z.boolean().optional(),
});
```

The form's `defaultValues` for non-required fields stay
empty / undefined. The submission helper strips
empty-string / undefined fields out of the body before
POSTing — Pydantic treats absent and explicit-null the
same.

### D7: Wizard collapses to a single step, but the file stays at `/tenants/new`

The four-step wizard's source code shrinks to ~40 lines:
one `<Input>` for `name`, one `<Button>` to submit, the
existing `formatApiError` helper for 422 surfacing. The
`STEPS`, `STEP_FIELDS`, `attemptedSteps`, and all
per-step branches are deleted. The TooltipProvider, the
Select / Checkbox / DatePicker imports, and the
sprint-3.10 RequiredMark / Revisión block are removed
from this file (the primitives stay in `components/ui/`
for the future edit screen).

### D8: Rebrand strategy — search-and-replace by string token, not regex

**Choice:** A handful of targeted `Edit` calls per file,
each replacing one specific string. We don't run a
project-wide `sed` because some occurrences of
"organización" or "organization" exist in backend
comments and code identifiers that MUST NOT change.

Strings to replace in `apps/web/src/`:

- `organización` → `empresa`
- `organizaciones` → `empresas`
- `Organización` → `Empresa`
- `Organizaciones` → `Empresas`
- `Crear organización` → `Crear empresa`
- `Tus organizaciones` → `Tus empresas`
- `Sin organización activa` → `Sin empresa activa`
- `Organización activa` → `Empresa activa`
- `Aún no tienes organizaciones` → `Aún no tienes empresas`
- `tu organización` → `tu empresa`
- `una organización` → `una empresa`
- `una empresa existente` (already says "empresa") —
  preserve

Code identifiers, route paths, type names, and import
specifiers stay.

### D9: Dashboard banner reads the active tenant's `ruc` / `fiscal_address`

A small client-side check: if `me.active_tenant` is set
and `getTenant(activeTenantId).ruc === null`, render an
`<Alert>` on the dashboard top with the "Completa tus
datos fiscales" copy. The banner is dismissable for the
session but reappears on reload until the data is
filled. The link points to `/empresa/editar` which is a
new stub route reading "Próximamente".

### D10: Sprint 3.6 pivots before it ships

The in-flight change `welcome-onboarding-rename-members`
has a proposal, tasks, and specs that all read
"organización". Since it has NOT been implemented yet
(the rename was *planned*, not *applied*), we edit those
artifacts to read "empresa" instead and update the
`organizations-frontend` capability name to
`empresas-frontend`. Route paths (`/organizations`,
`/organizations/new`) become `/empresas`, `/empresas/new`.
The carry-over task gains a bullet about the rebrand so
the rewrite preserves the new term.

## Risks / Trade-offs

- **[Risk]** The frontend Tenant type (generated from
  OpenAPI) becomes `Tenant & { ruc: string | null; ... }`.
  Code reading `tenant.ruc.toUpperCase()` blows up at
  runtime if the tenant is fiscally incomplete.
  **Mitigation:** TypeScript catches this at compile time
  thanks to `noUncheckedIndexedAccess`-adjacent strictness;
  the only consumer today is the wizard, which we are
  rewriting. Future consumers (invoicing) MUST guard.
- **[Risk]** Existing seed / E2E tests that POST a full
  payload now have to be re-read in light of Optional
  fields. **Mitigation:** Optional fields *accept* full
  payloads — the existing tests keep passing.
- **[Risk]** Pydantic v2 OpenAPI generation may emit
  `anyOf: [{type: string}, {type: null}]` for Optional —
  some openapi-typescript versions interpret that as
  `string | null` only with the `--default-non-nullable`
  flag. **Mitigation:** verify the regenerated
  `apps/web/src/api/schema.d.ts` has the expected
  Optional shape; adjust the generator config if
  needed.
- **[Risk]** The frontend search-and-replace misses a
  string and the user sees a half-rebranded UI.
  **Mitigation:** after the edits, grep
  `apps/web/src/` for `organizaci|Organizaci` (with
  exclusions for code paths) and confirm zero hits.
- **[Trade-off]** Backend tests for the create flow get
  longer because both "minimal" and "full" payloads need
  coverage. Worth it: a flow used at every signup needs
  both code paths tested.

## Migration Plan

1. Edit
   `apps/api/src/contexts/tenants/domain/tenant.py`:
   constructor + `register` accept Optional VOs.
2. Edit
   `apps/api/src/contexts/tenants/application/use_cases/create_tenant.py`:
   `CreateTenantCommand` fields become Optional; the use
   case parses VOs only when the value is present.
3. Edit
   `apps/api/src/contexts/tenants/adapters/outbound/persistence/sqlalchemy/tenant_repository.py`:
   `_load` and `add` handle None.
4. Edit
   `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`:
   `CreateTenantRequest` and `TenantResponse` fields
   except `name` become Optional.
5. Edit
   `apps/api/src/contexts/tenants/adapters/inbound/http/router.py`:
   the use case call passes Optional fields; the response
   mapper handles None.
6. Run the backend tests; fix breakages.
7. Regenerate the frontend OpenAPI client: `pnpm --filter
   web run openapi:generate`.
8. Edit `apps/web/src/features/tenants/schemas/index.ts`:
   `createTenantSchema` makes everything but `name`
   `.optional()`.
9. Rewrite `apps/web/src/routes/tenants/new.tsx` as a
   single-step form. Strip the wizard machinery.
10. Apply the rebrand string substitutions across
    `apps/web/src/`.
11. Add the dashboard "Completa tus datos fiscales"
    banner.
12. Add the stub `/empresa/editar` route.
13. Update
    `apps/web/tests/unit/routes/tenants-new.test.tsx`.
14. Pivot
    `openspec/changes/welcome-onboarding-rename-members/`
    proposal + tasks + specs from "organización" to
    "empresa".
15. Append the sprint 3.11 follow-up section to
    `docs/sprints/03-tenants-and-rls.md`.
16. Run `pnpm -C apps/web test|typecheck|lint` and the
    backend suite. All green.

**Rollback:** Revert the diff across backend + frontend
+ sprint 3.6 pivot. The DB schema was already nullable
before this change, so a rollback leaves the DB
unchanged. ADR-0034 stays merged for the historical
record; its supersedes link to ADR-0032 stays.

## Open Questions

- None within the scope agreed.
