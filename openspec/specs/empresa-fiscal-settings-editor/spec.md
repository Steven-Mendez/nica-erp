# empresa-fiscal-settings-editor Specification

## Purpose
TBD - created by archiving change add-empresa-fiscal-settings-form. Update Purpose after archive.
## Requirements
### Requirement: /empresa/settings renders the fiscal settings editor instead of a placeholder

`apps/web/src/routes/empresa/settings.tsx` SHALL render an
`<EmpresaFiscalSettingsForm>` inside the existing `<AppShell>`. The
form SHALL read the active empresa via
`useMeQuery().data?.active_tenant` and `useTenantQuery(activeId)`,
SHALL prefill all fields from that data, and SHALL submit via a
`useUpdateActiveTenantMutation` backed by the existing
`updateTenant(id, input)` endpoint.

The `Próximamente` placeholder card MUST be removed from this route.

#### Scenario: Route renders the editor for an authenticated operator with an active empresa

- **WHEN** an authenticated operator with `me.active_tenant === "tenant-a"` navigates to `/empresa/settings`
- **THEN** the route renders the four-section fiscal editor inside the AppShell, prefilled with `tenant-a`'s current fiscal data

#### Scenario: Route renders without crashing when active tenant data is still loading

- **WHEN** `useTenantQuery(activeId).isLoading` is true on first render
- **THEN** the route renders a skeleton (or spinner) inside the AppShell, not a crash, and the form mounts once the data resolves

### Requirement: Editor covers four field groups with documented validation

The editor SHALL contain four sections with the following fields and
validation rules:

1. **Identificación fiscal**
   - `ruc` (text, masked `NNN-NNNNNN-NNNNN`) — required;
     normalized on submit; format error renders Spanish
     `"Formato de RUC inválido."`
   - `regimen` (select) — required; values exactly:
     `"general" | "cuota_fija" | "pequeno_contribuyente"`.
   - `retenedor` (boolean toggle) — defaults to current value.

2. **Dirección fiscal**
   - `departamento` (select, 15 Nicaraguan options) — required.
   - `municipio` (select, dependent on `departamento`) — required;
     changing `departamento` clears `municipio` if the prior value is
     not valid for the new departamento.
   - `direccion` (textarea, ≥ 10 chars) — required;
     `"Ingresa al menos 10 caracteres."`

3. **Vigencia DGI**
   - `vigencia_inicio` (date) — required.
   - `vigencia_vencimiento` (date) — required; MUST be ≥
     `vigencia_inicio`; cross-field error: `"La fecha de vencimiento
     debe ser posterior al inicio."`
   - `resolucion_dgi` (text) — required.

4. **Contacto fiscal**
   - `correo_fiscal` (email) — required; standard email validation;
     `"Correo inválido."`
   - `telefono_fiscal` (tel, masked `+505 NNNN-NNNN`) — required;
     `"Formato de teléfono inválido."`

All copy is Spanish; all validation messages render in Spanish.

#### Scenario: Submitting without a RUC blocks submit and shows the inline error

- **WHEN** the operator clears `ruc` and presses Save
- **THEN** the submit button is disabled by validation OR the request is blocked, and the `ruc` field shows `"Formato de RUC inválido."` (or the required-field equivalent)

#### Scenario: Vencimiento before inicio shows a cross-field error

- **WHEN** the operator sets `vigencia_inicio = 2026-01-15` and `vigencia_vencimiento = 2026-01-01`
- **THEN** the form renders `"La fecha de vencimiento debe ser posterior al inicio."` and Save is blocked

#### Scenario: Changing departamento invalidates the current municipio

- **WHEN** the operator changes `departamento` from `Managua` to `León` and the previously-selected `municipio` is not a valid León municipio
- **THEN** `municipio` is cleared and the dropdown shows León's municipios

### Requirement: Permission gating renders the form read-only without tenant.update

The editor SHALL render in read-only mode when the operator lacks the `tenant.update` permission. When `useHasPermission("tenant.update")` returns false, the editor MUST render the four sections with every field `disabled` and the submit button hidden. A Spanish help-card SHALL render above the form
explaining that only the empresa owner or administrator can edit, with
the exact copy: `"Solo el propietario o administrador de la empresa
puede editar los datos fiscales."`

#### Scenario: Operator without permission sees the form disabled

- **WHEN** an authenticated operator without the `tenant.update` permission renders `/empresa/settings`
- **THEN** every field is `disabled`, the submit button is not rendered, and the Spanish help card is visible

#### Scenario: Operator with permission sees an editable form

- **WHEN** an authenticated operator with `tenant.update` renders `/empresa/settings`
- **THEN** all fields are editable, the submit button is visible, and the help card is hidden

### Requirement: Successful save updates the cache and clears the dashboard banner without reload

On a successful `PATCH /v1/tenants/{id}`, the mutation SHALL:

1. Update `qc.setQueryData(tenantKey(activeId), updatedTenant)` with
   the response payload.
2. Invalidate `myTenantsKey` via `qc.invalidateQueries`.
3. Render a Spanish success toast `"Datos fiscales guardados."`

The dashboard banner that watches `useTenantQuery(activeId)` for the
"datos fiscales incompletos" condition SHALL stop rendering once the
new payload satisfies its predicate, with no additional code path on
the editor side.

#### Scenario: Saving fiscal data hides the dashboard banner

- **WHEN** a tenant with previously-missing RUC saves a valid RUC + dirección + vigencia via the editor
- **THEN** navigating to `/dashboard` shows no `"Completa los datos fiscales"` banner, with no manual reload

### Requirement: 422 field errors map back to the form

The mutation's `onError` handler SHALL inspect a 422
`application/problem+json` response, iterate its `errors` array, and
for each entry call `form.setError(path, { type: "server", message })`
where:

- `path` is derived from the JSON-pointer (e.g. `/ruc` →
  `"ruc"`, `/fiscal_address/municipio` → `"municipio"`).
- `message` is the Spanish copy from the registry; if no entry,
  fall through to the backend `message` (already Spanish per the
  identity context's existing convention).

If any pointer cannot be mapped, the form renders a top-level
`<FormErrorAlert>` with the generic Spanish copy.

#### Scenario: 422 with /ruc pointer pins the error to the RUC field

- **WHEN** the backend returns 422 with `errors: [{ pointer: "/ruc", message: "RUC inválido", code: "ruc.format" }]`
- **THEN** `ruc` shows an inline error with that message and the rest of the form remains in its current state

### Requirement: 409 RUC collision renders as a form-level alert

The form SHALL render a top-of-form `<FormErrorAlert>` when the backend returns 409 with the RUC-uniqueness violation code, using the exact Spanish copy `"Este RUC ya está registrado en otra empresa."` The
individual `ruc` field SHALL NOT be marked as invalid (it is
syntactically fine; the collision is cross-record).

#### Scenario: RUC collision shows the form-level alert

- **WHEN** the backend returns 409 with the documented RUC-collision code
- **THEN** the top-of-form alert renders the documented Spanish copy and the `ruc` field stays in its normal (non-error) visual state

### Requirement: Integration tests cover the editor surface end-to-end

The editor SHALL be covered by Vitest integration tests under `apps/web/tests/integration/empresa-fiscal-settings/`. The suite MUST cover, at minimum:

- Form prefills from the active tenant's payload.
- Permission gating: form is disabled without `tenant.update`.
- Happy-path save updates the cache and toasts in Spanish.
- 422 with `/ruc` pointer pins to the field.
- 409 RUC collision renders the form-level alert.
- Departamento change invalidates the municipio.
- Cross-field date validation blocks Save.

#### Scenario: Integration tests are present in tests/integration

- **WHEN** the test suite under `apps/web/tests/integration/empresa-fiscal-settings/` is enumerated
- **THEN** at least one test file exists covering each of the scenarios above

