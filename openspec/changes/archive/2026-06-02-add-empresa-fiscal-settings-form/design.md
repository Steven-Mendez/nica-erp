## Context

The `/empresa/settings` route in
`apps/web/src/routes/empresa/settings.tsx` renders only a
`Próximamente` placeholder. The dashboard banner in
`apps/web/src/routes/dashboard.tsx` (and the route guard logic that
decides whether the banner shows) reads the active tenant via
`useTenantQuery(me.active_tenant)` and inspects fiscal fields to
decide whether to render the "Completa los datos fiscales" prompt.

The backend already exposes `PATCH /v1/tenants/{id}` with the fiscal
fields populated, and `GET /v1/tenants/{id}` returns them on the read
model. The `updateTenant` function in
`apps/web/src/features/tenants/api/endpoints.ts` already speaks this
endpoint; the gap is purely the editor UI and its validation.

The frontend layout rule from `docs/09-frontend.md` keeps slice
internals (components, schemas, hooks) under
`features/<slice>/` with within-slice imports relative; cross-slice
imports go through `@/features/<slice>` only where ESLint allows it.

## Goals / Non-Goals

**Goals:**

- Replace the `Próximamente` placeholder with a real editor that
  covers the fiscal-data fields required by the dashboard banner's
  satisfaction condition.
- Wire the editor end-to-end: read from `useTenantQuery`, validate
  with Zod, submit with `updateTenant`, invalidate the right query
  keys, surface field-level and form-level errors in Spanish.
- Honor the existing RBAC model: operators without `tenant.update`
  see the same fields in read-only mode with explanatory copy.
- Make the dashboard banner disappear automatically on save — no
  hard reload, no state-sync hacks.

**Non-Goals:**

- Adding new fields to the backend tenant aggregate. We surface what
  is already there.
- DGI integration (e.g. validating the RUC against a national
  registry). Out of scope; the form does format-level validation
  only.
- Multi-step wizard. A single page is simpler and matches what other
  empresa-scoped editors look like.
- Audit log / change history surface for fiscal-data edits. Defer.
- Department / municipality data sourcing — we assume a static list
  shipped with the SPA (15 departments, ~150 municipios). If a
  backend list becomes available later, the dropdown source flips
  to a query.

## Decisions

### Decision 1 — Single page, no wizard

The form has ~10 fields. Splitting them across steps adds clicks
without reducing complexity. Inline grouping (4 sections inside one
`<form>`) is the right shape.

### Decision 2 — Zod schema co-located in the tenants slice, not a shared schema

`apps/web/src/features/tenants/schemas/empresa-fiscal-settings.ts` is
the home. Co-locating keeps the schema next to the only consumer.
The schema MUST emit Spanish error messages via Zod's `errorMap` or
explicit `.refine` messages.

### Decision 3 — RUC and phone are validated by format, not by external service

- RUC: 14-digit format `NNN-NNNNNN-NNNNN` (Nicaraguan standard). The
  schema accepts both spaced and unspaced input and normalizes to
  the masked form before submission. We do not call an external
  DGI/RUC validator; the backend may reject an invalid RUC and the
  form maps that to a field-level error.
- Phone: `+505 NNNN-NNNN`. Same masking-on-input pattern.

### Decision 4 — Departamento / municipio are static dropdowns shipped with the SPA

A constant in `apps/web/src/features/tenants/data/nicaragua-geography.ts`
(or similar) defines 15 departamentos and their municipios. The
dropdown for municipio is dependent on the departamento value
(re-mounts options on change; if the departamento changes and the
current municipio is no longer valid, the field is cleared).

We chose a static list over a backend query because (a) the data
changes glacially and (b) one less network round-trip per render.

### Decision 5 — Permission gate via `useHasPermission("tenant.update")`

If the hook returns false, every form field gets `disabled` and the
submit button is hidden; an explanatory Spanish help card explains
who can edit. We do not block the route — read-only is a useful
view for non-admin operators.

If the hook does not yet exist by exact name in the rbac slice, this
change MAY introduce it; the underlying permission catalog already
defines `tenant.update`.

### Decision 6 — Mutation invalidates the active tenant key AND the my-tenants list

After a successful save:

- `qc.setQueryData(tenantKey(activeId), updatedTenant)` updates the
  cache without a refetch (the backend returns the updated read
  model).
- `qc.invalidateQueries({ queryKey: myTenantsKey })` so the picker
  reflects any visible-name changes that ripple through it.
- The dashboard banner watches `useTenantQuery(activeId)` and its
  satisfaction predicate, so the cache update is sufficient — no
  separate banner-specific signal.

### Decision 7 — Field-level errors from 422 map by JSON pointer in the problem doc

The backend's 422 problem document includes a `errors` array with
`{ pointer, message, code }` entries (current convention in the
identity context's validation responses). The form translates
pointers to RHF paths (`/ruc` → `ruc`, `/fiscal_address/municipio` →
`fiscalAddress.municipio`) and calls `form.setError(path, { type:
"server", message: spanishMessageForCode(code) ?? message })`.

If the pointer cannot be mapped to a known field, the error becomes
a form-level alert.

### Decision 8 — 409 RUC collision is a form-level alert, not a field error

A 409 with code `tenants.ruc_collision` (or whatever the backend
emits) does not pin to any single field cleanly (it's a uniqueness
violation across tenants). It renders as a top-of-form
`<FormErrorAlert>` with the Spanish copy `"Este RUC ya está
registrado en otra empresa."`

### Decision 9 — Banner satisfaction predicate stays in dashboard, not the editor

The dashboard already owns the predicate "this banner shows when
RUC + dirección + vigencia are missing." The editor does not know
about the banner. The mutation invalidation + the predicate's
re-evaluation on the new tenant payload is the only contract
between them.

## Risks / Trade-offs

- **Risk:** The static municipios list rots when Nicaraguan
  administrative boundaries change (rare but possible). →
  **Mitigation:** the data file is a single source; a future
  backend list can replace it with a query without changing the
  form. Tracked as an open question.
- **Risk:** Field-level error mapping silently drops errors when
  the JSON-pointer scheme changes on the backend. → **Mitigation:**
  a Vitest integration test fixture pins the expected pointers; any
  shape change forces an update.
- **Risk:** `useHasPermission` may have a different name than
  assumed. → **Mitigation:** implementation task verifies the
  actual export and updates the spec wording if needed.
- **Risk:** The form is large; render performance with RHF +
  controlled inputs has been an issue elsewhere in the codebase. →
  **Mitigation:** use the existing shadcn `<Input>` + `<Select>`
  primitives the rest of the SPA uses; no novel controls. RHF's
  default uncontrolled mode is sufficient.
- **Trade-off:** No DGI validation means an operator can save a
  malformed-but-passing RUC and only learn it's wrong later. We
  accept this for the MVP; DGI integration is a known follow-up.

## Migration Plan

Single deploy. The placeholder route is replaced. No backend
changes. Rollback: revert the route file to the placeholder version
(one-file revert).

## Open Questions

- Should the form persist a draft to local state across navigation
  away (so an operator who navigates accidentally doesn't lose their
  input)? Not implemented in the MVP; revisit if the form's length
  causes complaints.
- Should there be a "Datos completos" status badge on the editor
  itself, mirroring the dashboard banner? Probably useful, deferred
  to product review.
- Confirm the exact backend problem code for a duplicate RUC.
- Confirm whether `useHasPermission` is the actual hook name in the
  RBAC slice.
