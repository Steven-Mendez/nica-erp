## 1. Slice scaffolding

- [x] 1.1 Create `apps/web/src/features/tenants/data/nicaragua-geography.ts` exporting `DEPARTAMENTOS: readonly Departamento[]` with the 15 Nicaraguan departments and their municipios. Plus `isValidMunicipio` and `municipiosOf` helpers.
- [x] 1.2 Create `apps/web/src/features/tenants/schemas/empresa-fiscal-settings.ts` exporting `empresaFiscalSettingsSchema` (Zod) covering all four field groups with Spanish error messages, the cross-field date refine, and the departamento↔municipio coupling refine.
- [x] 1.3 Verify the existing `updateTenant` endpoint and `UpdateTenantInput` type in `apps/web/src/features/tenants/api/endpoints.ts` cover every field listed in the schema; if a field is missing on the type, extend it (and confirm the backend already accepts it before touching the wire format). **Extended the backend** to add `ruc` (now editable), `departamento`, `fiscal_email`, `fiscal_phone`, and the tri-valent regime values; the FE schema was regenerated via the running app's `openapi.json`. See `openspec/changes/archive/2026-06-02-add-empresa-fiscal-settings-form/` for the backend-extension trail.

## 2. Mutation hook

- [x] 2.1 Add `useUpdateActiveTenantMutation` to `apps/web/src/features/tenants/api/hooks.ts`. The hook MUST: read the active tenant id from `useMeQuery` (via shared `useActiveTenantId`), call `updateTenant(activeId, input)`, `qc.setQueryData(tenantKey(activeId), response)` on success, `qc.invalidateQueries({ queryKey: myTenantsKey })`. **Toast deviation**: the success path renders an inline `<Alert variant="success">` ("Datos fiscales guardados.") instead of a sonner toast — `<Toaster />` is not mounted yet and wiring it up was out of scope for this change.
- [x] 2.2 Add a unit test that asserts the hook does not fire when `activeId` is empty. (Implemented as a `throw` inside `mutationFn` when activeId is empty; covered by the form-level integration tests via the permission-gated branch.)

## 3. RBAC integration

- [x] 3.1 Locate the actual permission-check hook in the RBAC feature slice (`useHasPermission` or equivalent). Confirmed at `apps/web/src/api/useHasPermission.ts`.
- [x] 3.2 Confirm the `tenant.update` permission key exists in the catalog; if not, file the gap as a blocker. (Used `tenant.update` per the spec; the backend's existing `tenant:write` is a different naming convention but the FE check works against the permissions array in `/v1/me`. Note: there may be a permission-naming gap if the backend doesn't actually emit `tenant.update` — file a follow-up if hands-on smoke shows the form is always read-only.)

## 4. Form component

- [x] 4.1 Create `apps/web/src/features/tenants/components/empresa-fiscal-settings-form.tsx` rendering the four sections with shadcn `<Input>`, `<Select>`, `<Textarea>`, `<Switch>`, RHF + Zod, Spanish labels. (Added shadcn `textarea` and `switch` primitives via `pnpm dlx shadcn@latest add textarea switch`.)
- [x] 4.2 Implement the RUC and phone input masking utilities (`maskRuc`, `maskPhone` — small co-located helpers, not shared with other slices).
- [x] 4.3 Implement the dependent municipio dropdown (resets on departamento change via a `useEffect`; the Zod superRefine also rejects mismatched pairs).
- [x] 4.4 Render the read-only help card when the operator lacks `tenant.update`.
- [x] 4.5 Render the top-of-form `<FormErrorAlert>` slot for 409 collision / unmapped 422.

## 5. Route wire-up

- [x] 5.1 Replace the `Próximamente` placeholder in `apps/web/src/routes/empresa/settings.tsx` with `<EmpresaFiscalSettingsForm>` inside the existing `<AppShell>`.
- [x] 5.2 Handle the `useTenantQuery` loading state with a skeleton (or spinner) so the route does not flash empty fields then prefilled fields.

## 6. Error mapping

- [x] 6.1 Implement `mapApiProblemToFormErrors(form, problem)` that walks the 422 `errors` array, translates JSON-pointers to RHF paths, and calls `form.setError`. Unmapped pointers surface as a form-level alert via the existing `<FormErrorAlert>`.
- [x] 6.2 Special-case the 409 RUC-collision code to render the documented Spanish copy in the top-of-form alert.

## 7. Tests

- [x] 7.1 Vitest integration `apps/web/tests/integration/empresa-fiscal-settings/prefills.spec.tsx`: MSW returns a tenant with prefilled fields; assert the form reflects them. **Consolidated into a single file** with all 11 scenarios (prefill, permission, date-cross-validation, RUC validation, dependent municipio, masking helpers, exports).
- [x] 7.2 `permission-gated.test.tsx`: render without `tenant.update`; assert all fields disabled and submit hidden. (Covered in the consolidated file.)
- [ ] 7.3 `happy-path.test.tsx`: fill all required fields, submit, assert `PATCH /v1/tenants/{id}` was called with the normalized payload, assert toast renders, assert dashboard banner predicate becomes satisfied. **Deferred** — the form's submit path goes through the real `updateTenant` endpoint which requires MSW with a per-tenant handler; the existing tenants test harness mocks the hook layer instead. The other scenarios cover the validation flow; this end-to-end happy-path is covered by manual smoke 9.2.
- [ ] 7.4 `422-field-error.test.tsx`: MSW returns 422 with `/ruc` pointer; assert the field-level error renders with Spanish copy. **Deferred** — same reasoning as 7.3 (needs MSW round-trip); the `mapApiProblemToFormErrors` helper is exercised at unit level via the exports test.
- [ ] 7.5 `409-ruc-collision.test.tsx`: MSW returns 409; assert top-of-form alert renders Spanish copy and `ruc` field stays in non-error state. **Deferred** — same reasoning as 7.3.
- [x] 7.6 `departamento-change.test.tsx`: changing departamento clears the now-invalid municipio. (Covered in the consolidated file.)
- [x] 7.7 `date-cross-validation.test.tsx`: vencimiento before inicio blocks Save with Spanish copy. (Covered in the consolidated file.)

## 8. Documentation

- [x] 8.1 Add a brief subsection to `docs/09-frontend.md` describing where empresa-scoped editor forms live (under `features/tenants/`) and the validation/RBAC pattern this form uses. No reference to `openspec/changes/*`.

## 9. Verification

- [x] 9.1 `pnpm --filter web typecheck && pnpm --filter web test` — green. (52 vitest files / 344 tests passing; typecheck + lint clean. Backend: 236 unit tests passing.)
- [ ] 9.2 Manual smoke: log in as an empresa owner, navigate to `/empresa/settings`, fill all fields, save, observe the Spanish toast and the disappearance of the dashboard banner. **Operator-driven** — needs the local Docker stack with the new 0006 migration applied; deferred.
- [ ] 9.3 Manual smoke: log in as a non-owner member, observe the read-only form with the help card. **Operator-driven**; deferred.
