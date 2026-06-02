## Why

`apps/web/src/routes/empresa/settings.tsx` currently renders a
`Próximamente` placeholder card. The dashboard already shows a
"Completa los datos fiscales" banner that links the operator to this
route, but landing there is a dead end: the operator cannot enter the
RUC, fiscal address, regime, or DGI vigencia that the banner asks for.
This is the primary feature blocker called out in the QA audit's
"Gaps Inside Existing Features" section.

The backend side is already in place. `PATCH /v1/tenants/{id}` (the
`tenants-http` router under
`apps/api/src/contexts/tenants/adapters/inbound/http/router.py`)
accepts the fiscal-data fields, and the read model returned by
`GET /v1/tenants/{id}` already includes them. The work is therefore
**a frontend form against existing backend contracts**, not a new
capability on the API side.

## What Changes

- Replace the `Próximamente` placeholder in
  `apps/web/src/routes/empresa/settings.tsx` with a real editor route
  composed of a single `<EmpresaFiscalSettingsForm>` rendered inside
  the existing `AppShell`. The form reads the active empresa via
  `useMeQuery().data.active_tenant` and `useTenantQuery(activeId)`,
  and submits via a new `useUpdateActiveTenantMutation` hook backed by
  the existing `updateTenant(id, input)` endpoint in
  `apps/web/src/features/tenants/api/endpoints.ts`.
- The form covers four field groups, matching the existing fiscal
  fields on the backend tenant aggregate:
  1. **Identificación fiscal** — RUC (text, masked `XXX-XXXXXX-XXXXX`),
     régimen tributario (select: `General`, `Cuota Fija`, `Pequeño
     Contribuyente`), retenedor (toggle).
  2. **Dirección fiscal** — departamento (select), municipio (select,
     dependent on departamento), dirección detallada (textarea).
  3. **Vigencia DGI** — fecha de inicio (date), fecha de vencimiento
     (date), número de resolución (text).
  4. **Contacto fiscal** — correo de notificaciones DGI (email),
     teléfono de contacto fiscal (tel, masked `+505 XXXX-XXXX`).
- Validation: a Zod schema co-located at
  `apps/web/src/features/tenants/schemas/empresa-fiscal-settings.ts`
  (mirroring the existing slice layout where schemas live under the
  feature). All copy is Spanish (per the project Spanish-UI rule);
  error messages localized in the schema.
- The form integrates with the dashboard banner: on successful save,
  the dashboard banner ("Completa los datos fiscales") disappears
  because the RUC + dirección + vigencia presence is the banner's
  trigger condition. The banner already reads `useTenantQuery` —
  the mutation MUST invalidate the active `tenantKey(id)` so the
  dashboard re-renders without a hard reload.
- Permissions: editing fiscal data requires `tenant.update`. Operators
  without the permission see the form fields in read-only mode and a
  Spanish help-text card explaining that only the empresa owner /
  admin can edit. The permission check uses the existing
  `useHasPermission` hook (whatever it is named in the rbac feature
  slice) — no new permission keys are introduced.
- Failure modes:
  - 422 with field-level `application/problem+json` errors map back
    to the corresponding form field (`form.setError`).
  - 409 (e.g. RUC collision if the backend enforces uniqueness) shows
    an inline form-level alert: "Este RUC ya está registrado en otra
    empresa."
  - 403 (operator lost permission mid-session) renders the
    `RouteForbiddenCard` introduced in
    `harden-tenant-isolation-and-errors` — depending on which change
    lands first, the form may temporarily render its own forbidden
    card.

## Capabilities

### New Capabilities

- `empresa-fiscal-settings-editor`: the editor route's structure,
  field set, validation rules, permission gating, save semantics, and
  Spanish copy contract. This is a new capability — the existing
  `tenants-*` specs live in the archive (they cover the backend
  contracts) and the SPA editor has no current spec.

### Modified Capabilities

_(none — the backend `PATCH /v1/tenants/{id}` contract is unchanged.
The dashboard fiscal-banner behavior already follows from existing
data, no spec update needed.)_

## Impact

- **Code:**
  - `apps/web/src/routes/empresa/settings.tsx` — replace placeholder
    with the editor.
  - `apps/web/src/features/tenants/api/hooks.ts` — add
    `useUpdateActiveTenantMutation` (thin wrapper that reads the
    active tenant id, calls `updateTenant`, invalidates
    `tenantKey(id)` + `myTenantsKey`).
  - `apps/web/src/features/tenants/components/` — new
    `empresa-fiscal-settings-form.tsx` (within-slice imports are
    relative, per the project ESLint boundary rule).
  - `apps/web/src/features/tenants/schemas/empresa-fiscal-settings.ts`
    — Zod schema.
- **Tests:** Vitest integration under
  `apps/web/tests/integration/empresa-fiscal-settings/` covering
  read-only mode without permission, happy-path save, 422 field
  mapping, 409 RUC collision, and banner-clears-on-save.
- **APIs:** none. `PATCH /v1/tenants/{id}` is already in place.
- **Backend:** no changes.
- **Docs:** `docs/09-frontend.md` gets a short paragraph noting that
  empresa-scoped editor forms live under `features/tenants/`.
