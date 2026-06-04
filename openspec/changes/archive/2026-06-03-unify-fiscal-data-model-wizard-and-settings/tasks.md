## 1. Canonical enum / schema

- [x] 1.1 `DEPARTAMENTOS` and `Departamento` (TS union) ship from `apps/web/src/features/tenants/lib/departamentos.ts` — 17 values alphabetised.
- [x] 1.2 Backend `Departamento` value object lives in `apps/api/src/contexts/tenants/domain/departamento.py` with the matching 17-value `KNOWN_DEPARTAMENTOS` frozenset. Exported from `contexts.tenants.domain.__init__`.
- [x] 1.3 `CreateTenantRequest.validate_departamento` + `UpdateTenantRequest.validate_departamento` pin the field to the catalog with Spanish copy `Departamento inválido`.

## 2. Backend — settings vs create parity

- [x] 2.1 `POST /v1/tenants` and `PATCH /v1/tenants/{id}` both accept `departamento` and `municipality` (already true; the new validator tightens `departamento`).
- [x] 2.2 OpenAPI examples updated via field-level `examples=["Managua"]` and the new request-schema constraint.

## 3. Frontend — wizard step 2 rewrite

- [x] 3.1 The wizard's old `municipality` combobox is now a `Departamento` combobox sourced from `DEPARTAMENTOS` (17 options). Persists to the form field `departamento`.
- [x] 3.2 New `Municipio` free-text input below `Departamento`, persists to `municipality` with placeholder `Ej: Distrito V`.
- [x] 3.3 `buildPayload` sends both `departamento` and `municipality` to `POST /v1/tenants`; RUC is normalised via `normalizeRuc` before send.
- [x] 3.4 Progress sidebar copy / `FIELD_LABELS` extended with `departamento → "Departamento"`.

## 4. Frontend — RUC placeholder + strip helper

- [x] 4.1 `apps/web/src/features/tenants/lib/ruc.ts` already exports `RUC_PLACEHOLDER` and `normalizeRuc`.
- [x] 4.2 Wizard step-1 RUC input + `empresa-fiscal-settings-form.tsx` RUC input both use `RUC_PLACEHOLDER`. Submit transforms via `normalizeRuc` in the wizard payload builder; the settings editor already canonicalises via `maskRuc`.
- [x] 4.3 `apps/web/tests/unit/features/tenants/ruc.test.ts` covers strip, uppercase, idempotency, and the documented placeholder round-trip.

## 5. Frontend — DGI date labels unified

- [x] 5.1 Wizard step 3 labels: `Inicio de vigencia` / `Vencimiento` (renamed in a previous edit).
- [x] 5.2 `apps/web/src/routes/empresa/index.tsx` renders `Vigencia: <inicio> → <vencimiento>` (composite label — both dates visible on one line). The settings editor uses the literal `Inicio de vigencia` / `Vencimiento` labels.

## 6. Tests

- [x] 6.1 Backend unit `test_departamento.py` accepts all 17 values; `test_create_tenant_request_schema.py` adds `test_unknown_departamento_is_rejected_with_spanish_copy` + `test_departamento_from_catalog_is_accepted` + `test_municipality_is_free_text`.
- [x] 6.2 Frontend Vitest `tenants-schemas.test.ts` adds `rejects a departamento outside the canonical catalog`, `accepts every canonical departamento`, and `accepts a free-text municipality`.
- [x] 6.3 The settings editor already passes its existing spec suite; its dependent-municipio dropdown is preserved (richer UX than the wizard's free text); `nicaragua-geography.ts` now carries RAAN + RAAS entries with their municipios so the editor also covers all 17 deps.
- [ ] 6.4 Browser smoke — deferred (no live dev session in this batch run).

## 7. Validation

- [x] 7.1 `openspec validate unify-fiscal-data-model-wizard-and-settings --strict` exits 0.
