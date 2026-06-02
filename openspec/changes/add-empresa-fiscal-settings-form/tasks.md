## 1. Slice scaffolding

- [ ] 1.1 Create `apps/web/src/features/tenants/data/nicaragua-geography.ts` exporting `DEPARTAMENTOS: readonly Departamento[]` with the 15 Nicaraguan departments and their municipios.
- [ ] 1.2 Create `apps/web/src/features/tenants/schemas/empresa-fiscal-settings.ts` exporting `empresaFiscalSettingsSchema` (Zod) covering all four field groups with Spanish error messages and the cross-field date refine.
- [ ] 1.3 Verify the existing `updateTenant` endpoint and `UpdateTenantInput` type in `apps/web/src/features/tenants/api/endpoints.ts` cover every field listed in the schema; if a field is missing on the type, extend it (and confirm the backend already accepts it before touching the wire format).

## 2. Mutation hook

- [ ] 2.1 Add `useUpdateActiveTenantMutation` to `apps/web/src/features/tenants/api/hooks.ts`. The hook MUST: read the active tenant id from `useMeQuery`, call `updateTenant(activeId, input)`, `qc.setQueryData(tenantKey(activeId), response)` on success, `qc.invalidateQueries({ queryKey: myTenantsKey })`, and toast `"Datos fiscales guardados."`
- [ ] 2.2 Add a unit test that asserts the hook does not fire when `activeId` is empty.

## 3. RBAC integration

- [ ] 3.1 Locate the actual permission-check hook in the RBAC feature slice (`useHasPermission` or equivalent). If the exact name differs, update the spec wording to match the actual export before continuing.
- [ ] 3.2 Confirm the `tenant.update` permission key exists in the catalog; if not, file the gap as a blocker (this is the only permission the form needs).

## 4. Form component

- [ ] 4.1 Create `apps/web/src/features/tenants/components/empresa-fiscal-settings-form.tsx` rendering the four sections with shadcn `<Input>`, `<Select>`, `<Textarea>`, `<Switch>`, RHF + Zod, Spanish labels.
- [ ] 4.2 Implement the RUC and phone input masking utilities (small co-located helpers, not shared with other slices).
- [ ] 4.3 Implement the dependent municipio dropdown (resets on departamento change, validates existing value belongs to the new departamento).
- [ ] 4.4 Render the read-only help card when the operator lacks `tenant.update`.
- [ ] 4.5 Render the top-of-form `<FormErrorAlert>` slot for 409 collision / unmapped 422.

## 5. Route wire-up

- [ ] 5.1 Replace the `Próximamente` placeholder in `apps/web/src/routes/empresa/settings.tsx` with `<EmpresaFiscalSettingsForm>` inside the existing `<AppShell>`.
- [ ] 5.2 Handle the `useTenantQuery` loading state with a skeleton (or spinner) so the route does not flash empty fields then prefilled fields.

## 6. Error mapping

- [ ] 6.1 Implement `mapApiProblemToFormErrors(form, problem)` that walks the 422 `errors` array, translates JSON-pointers to RHF paths, and calls `form.setError`. Unmapped pointers surface as a form-level alert.
- [ ] 6.2 Special-case the 409 RUC-collision code to render the documented Spanish copy in the top-of-form alert.

## 7. Tests

- [ ] 7.1 Vitest integration `apps/web/tests/integration/empresa-fiscal-settings/prefills.test.tsx`: MSW returns a tenant with prefilled fields; assert the form reflects them.
- [ ] 7.2 `permission-gated.test.tsx`: render without `tenant.update`; assert all fields disabled and submit hidden.
- [ ] 7.3 `happy-path.test.tsx`: fill all required fields, submit, assert `PATCH /v1/tenants/{id}` was called with the normalized payload, assert toast renders, assert dashboard banner predicate becomes satisfied.
- [ ] 7.4 `422-field-error.test.tsx`: MSW returns 422 with `/ruc` pointer; assert the field-level error renders with Spanish copy.
- [ ] 7.5 `409-ruc-collision.test.tsx`: MSW returns 409; assert top-of-form alert renders Spanish copy and `ruc` field stays in non-error state.
- [ ] 7.6 `departamento-change.test.tsx`: changing departamento clears the now-invalid municipio.
- [ ] 7.7 `date-cross-validation.test.tsx`: vencimiento before inicio blocks Save with Spanish copy.

## 8. Documentation

- [ ] 8.1 Add a brief subsection to `docs/09-frontend.md` describing where empresa-scoped editor forms live (under `features/tenants/`) and the validation/RBAC pattern this form uses. No reference to `openspec/changes/*`.

## 9. Verification

- [ ] 9.1 `pnpm --filter web typecheck && pnpm --filter web test` — green.
- [ ] 9.2 Manual smoke: log in as an empresa owner, navigate to `/empresa/settings`, fill all fields, save, observe the Spanish toast and the disappearance of the dashboard banner.
- [ ] 9.3 Manual smoke: log in as a non-owner member, observe the read-only form with the help card.
