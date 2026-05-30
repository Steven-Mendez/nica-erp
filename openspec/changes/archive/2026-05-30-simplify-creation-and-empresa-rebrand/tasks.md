## 1. Sprint doc

- [x] 1.1 Append "Sprint follow-up — Empresa rebrand + soft-creation (sprint 3.11, 2026-05-28)" to `docs/sprints/03-tenants-and-rls.md`. Cover motivation, scope (Pydantic + aggregate + repo + frontend), non-goals (no migration, no backend rename, no edit UI).

## 2. Backend: Tenant aggregate

- [x] 2.1 In `apps/api/src/contexts/tenants/domain/tenant.py`, change the `__init__` signature so `ruc`, `regime`, `municipality`, `authorization_dgi`, and `fiscal_address` accept `Optional[...]`. Update the `register` classmethod the same way. Update the read-only properties to return `Optional[VO] | Optional[str]`. The slot tuple, the `__slots__`, the equality semantics, and the `TenantCreated` event payload stay.
- [x] 2.2 Verify `TenantCreated` event consumers tolerate Optional fields. If `TenantCreated` carries the same fields (likely yes), update its dataclass too.

## 3. Backend: CreateTenantCommand + use case

- [x] 3.1 In `apps/api/src/contexts/tenants/application/use_cases/create_tenant.py`, change `CreateTenantCommand` so all fields except `actor_user_id`, `name`, and `is_withholder` are `Optional[...]` with `default=None` (the dataclass needs the field reordering since defaulted fields come last).
- [x] 3.2 In `CreateTenant.execute`, parse VOs conditionally: `ruc=Ruc.parse(cmd.ruc) if cmd.ruc is not None else None`, etc. The full `Tenant.register(...)` call passes through the resulting Optionals.

## 4. Backend: Repository

- [x] 4.1 In `apps/api/src/contexts/tenants/adapters/outbound/persistence/sqlalchemy/tenant_repository.py`, update `_load` so each fiscal column becomes Optional: `Ruc(row["ruc"]) if row["ruc"] is not None else None`, and equivalent for regime, municipality, authorization_dgi (which is a composite — None if all three columns are NULL), and fiscal_address.
- [x] 4.2 Update `add` (and `update` if it exists) so the SQL bind dict passes `None` for the columns when the aggregate's field is `None`.

## 5. Backend: HTTP layer

- [x] 5.1 In `apps/api/src/contexts/tenants/adapters/inbound/http/schemas.py`, make every field on `CreateTenantRequest` optional except `name` (use `Optional[T] = Field(default=None, ...)`). Keep `is_withholder: bool = Field(default=False)`. Mirror the Optional shape on `TenantResponse` and `AuthorizationDgiPayload` (the latter only when nested under an Optional parent).
- [x] 5.2 In `apps/api/src/contexts/tenants/adapters/inbound/http/router.py`, update `create_tenant` so the `CreateTenantCommand` it builds passes through Optional values. Update `_tenant_to_response` (and `_dgi_to_vo` if present) to handle None inputs.

## 6. Backend: Tests

- [x] 6.1 Add `apps/api/tests/unit/contexts/tenants/domain/test_aggregates.py` cases for: (a) `Tenant.register` with only `name` produces a valid aggregate with all fiscal fields None; (b) mixing provided + None fields works; (c) malformed RUC still raises `ValueError` at the VO.
- [x] 6.2 Add `apps/api/tests/integration/contexts/tenants/test_tenant_repository.py` case: insert a tenant with NULL fiscal columns, round-trip via `get(id)`, assert all fiscal fields are None.
- [x] 6.3 Add `apps/api/tests/e2e/contexts/tenants/` case (or update existing): `POST /v1/tenants` with `{"name": "X"}` only returns 201 with null fiscal fields.
- [x] 6.4 Run `cd apps/api && uv run pytest`. All existing tests must still pass; the new ones must pass too.

## 7. OpenAPI client regen

- [x] 7.1 Run `pnpm --filter web run openapi:generate`. Inspect `apps/web/src/api/schema.d.ts`: confirm `CreateTenantRequest.ruc?: string | null`, `TenantResponse.ruc?: string | null` and equivalent for the other fiscal fields. If the generator emits a non-null Optional only (no `| null`), the codegen config may need a flag — verify and adjust.

## 8. Frontend: Zod relaxation

- [x] 8.1 In `apps/web/src/features/tenants/schemas/index.ts`, rewrite `createTenantSchema` so only `name` is required. Use `.optional()` on `ruc`, `regime`, `municipality`, `authorization_dgi`, `fiscal_address`, `is_withholder`. Keep each constraint's Spanish message — they only fire when the user explicitly provides the field.

## 9. Frontend: Wizard rewrite

- [x] 9.1 Rewrite `apps/web/src/routes/tenants/new.tsx` as a single-step form. Strip: `STEPS`, `STEP_FIELDS`, `attemptedSteps`, the per-step branch rendering, the `TooltipProvider`, the Select / Checkbox / DatePicker / RequiredMark / formatReviewDate code paths, the Revisión block. Keep: the `useDocumentTitle("Crear empresa")` call (updated copy), `useForm` with `mode: "onTouched"`, the `formatApiError` helper (still useful for the simpler form), the `useCreateTenantMutation` + `useSwitchTenantMutation` orchestration. Final file size target: ~80–120 lines. (Superseded by sprint 3.12 `tenants-new-wizard-skippable`: the wizard returned, but as a fully skippable variant. The Zod relaxation + backend-Optional contract from this change is what makes the skip work.)
- [x] 9.2 The single field renders as: `<Label htmlFor="name">Nombre</Label> <RequiredMark />` + `<Input id="name" placeholder="Nombre de tu empresa" {...register("name")} />`. The submit button reads "Crear empresa" and is disabled while either mutation is pending. (Superseded by 3.12; primary submit retains the "Crear empresa" label on the last step.)

## 10. Frontend: Rebrand "organización" → "empresa"

- [x] 10.1 In `apps/web/src/routes/tenants/index.tsx`: `useDocumentTitle("Tus organizaciones")` → `"Tus empresas"`, heading `Tus organizaciones` → `Tus empresas`, CTA `Crear organización` → `Crear empresa`, alert `No se pudieron cargar tus organizaciones.` → `No se pudieron cargar tus empresas.`, empty-state `Aún no tienes organizaciones` → `Aún no tienes empresas`, helper `Crea una organización para empezar a facturar.` → `Crea una empresa para empezar a facturar.`.
- [x] 10.2 In `apps/web/src/routes/tenants/members.tsx`: `Miembros activos de esta organización.` → `Miembros activos de esta empresa.`.
- [x] 10.3 In `apps/web/src/routes/onboarding.tsx`: code comment `Crear empresa  → routes to the tenant-create wizard.` stays (already correct). `Empecemos configurando tu organización.` → `Empecemos configurando tu empresa.`, `Crea tu organización` → `Crea tu empresa`, `Configura los datos fiscales de tu organización para empezar a operar.` → `Configura los datos fiscales de tu empresa para empezar a operar.`, `Crear organización` → `Crear empresa`, `Pega el código que te enviaron para unirte a una organización existente.` → `Pega el código que te enviaron para unirte a una empresa existente.`.
- [x] 10.4 In `apps/web/src/routes/account.tsx`: `Tu perfil, la organización activa y tus permisos.` → `Tu perfil, la empresa activa y tus permisos.`, `Organización activa` (CardTitle) → `Empresa activa`, `La organización asociada a tu sesión.` → `La empresa asociada a tu sesión.`, `Sin organización activa.` → `Sin empresa activa.`, `Crear organización` → `Crear empresa`, `Acciones permitidas en la organización activa.` → `Acciones permitidas en la empresa activa.`.
- [x] 10.5 In `apps/web/src/components/app-sidebar/tenant-switcher.tsx`: `title="Sin organización activa"` → `"Sin empresa activa"`, the visible `Sin organización activa` → `Sin empresa activa`, `title={active?.name ?? "Organización"}` → `"Empresa"`, the `Organización activa` label → `Empresa activa`.
- [x] 10.6 In `apps/web/src/routes/tenants/new.tsx` (already heavily rewritten in §9): ensure the rebrand is consistent in the rewritten body (no leftover "organización"). Inline tooltip / Info copy references to "organización" in the route file's text should also pivot.
- [x] 10.7 In `apps/web/src/features/tenants/schemas/index.ts`: error message `"La dirección fiscal es obligatoria."` is fine (already empresa-neutral); no edit needed.
- [x] 10.8 After all edits, run `rg "organizaci|Organizaci" apps/web/src/` and confirm zero hits in user-visible string positions. Hits in `// comment` lines that describe the backend "Tenant" are acceptable IF they don't surface to the user.

## 11. Frontend: Dashboard banner

- [x] 11.1 In `apps/web/src/routes/dashboard.tsx` (or wherever the dashboard root component is), use the existing `getTenant(activeTenantId)` query (or extend `useMeQuery`) to read the active tenant. If `tenant.ruc === null` OR `tenant.fiscal_address === null`, render `<Alert>` at the top with `<AlertDescription>Completa los datos fiscales de tu empresa para emitir facturas.</AlertDescription>` followed by `<Link to="/empresa/editar">Completar ahora</Link>`.

## 12. Frontend: Stub edit route

- [x] 12.1 Create `apps/web/src/routes/empresa/editar.tsx` rendering a centered Card with title "Editar empresa" and body "Próximamente — esta pantalla estará disponible en una próxima actualización." Register the route in the router config the same way the existing routes are registered.

## 13. Pivot sprint 3.6

- [x] 13.1 In `openspec/changes/welcome-onboarding-rename-members/proposal.md`, replace every occurrence of "organización"/"Organización"/"organizations"/"Organizations" with the empresa equivalent in user-visible-copy contexts. Code identifier names (`features/organizations/`, `OrganizationSwitcher`, `Organization`, `/organizations`) become the empresa equivalents (`features/empresas/`, `EmpresaSwitcher`, `Empresa`, `/empresas`) since this change has not yet been implemented. Backend names stay.
- [x] 13.2 In `openspec/changes/welcome-onboarding-rename-members/tasks.md`, apply the same pivot. Update task 12.1's bullets so they reference "empresa" carry-over instead of "organización".
- [x] 13.3 Rename `openspec/changes/welcome-onboarding-rename-members/specs/organizations-frontend/spec.md` → `.../empresas-frontend/spec.md` and pivot every copy reference inside. The capability name in `proposal.md` updates to `empresas-frontend`.

## 14. Update frontend tests

- [x] 14.1 Rewrite `apps/web/tests/unit/routes/tenants-new.test.tsx` for the single-step form: (a) one input "Nombre" with a `*` mark, (b) submitting "Mi Empresa" calls the mutation with `{ name: "Mi Empresa" }` only, (c) no Régimen / Municipio / DatePicker / Checkbox / Revisión in the DOM. (Superseded by sprint 3.12 wizard-skippable tests — the test now covers the skippable wizard variant.)
- [x] 14.2 Update existing tests that asserted "organización" copy: `apps/web/tests/unit/routes/onboarding.test.tsx` (Crear organización → Crear empresa label). Welcome / Health / Confirm tests don't touch this copy.

## 15. Verify

- [x] 15.1 `pnpm -C apps/web test|typecheck|lint` all green.
- [x] 15.2 `cd apps/api && uv run pytest` all green.
- [x] 15.3 `openspec validate simplify-creation-and-empresa-rebrand` is valid.
- [x] 15.4 `rg "organizaci" apps/web/src/` returns zero user-visible matches.

## 16. Smoke

- [x] 16.1 In the dev server: open `http://localhost:5173/tenants/new`, type a name only, click "Crear empresa", verify the SPA lands on `/dashboard` with the "Completa los datos fiscales" banner visible.
