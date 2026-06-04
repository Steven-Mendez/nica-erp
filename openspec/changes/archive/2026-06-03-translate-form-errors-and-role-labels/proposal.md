## Why

Two Spanish-rule violations (F-010 and F-033) leak English into a
Spanish-only product:

1. **F-010** — `/tenants/new` step 3 (Autorización DGI). With all
   fields blank, clicking Continuar renders the field error verbatim
   English: `Required`. Likely a bare zod default that was never
   wrapped.
2. **F-033** — `/tenants` empresa-list cards render the raw English
   role string `owner` underneath each empresa name. The sidebar
   workspace switcher and the members table already map role codes
   to Spanish (`Propietario`, `Contador`, etc.); the empresa-list
   card view does not.

This change unifies the role label map and wraps the form-error
defaults, ensuring no English appears in any user-facing string.

## What Changes

### Frontend — single role-label map

- Move the `ROLE_LABELS` mapping from
  `apps/web/src/features/tenants/components/InvitationsTable.tsx:30`
  into a shared module
  `apps/web/src/features/tenants/lib/role-labels.ts`. Export a typed
  `roleLabel(role: TenantRole): string` helper that returns the
  Spanish label and falls back to the raw role only as a last resort.
- Reuse it in:
  - `apps/web/src/components/app-sidebar/tenant-switcher.tsx` (today
    has its own inline map — replace).
  - `apps/web/src/routes/tenants/index.tsx` (the empresa-list cards
    — today renders the raw role).
  - The members table.
- Ensure the map covers every backend-issued role:
  `owner → Propietario`, `admin → Administrador`,
  `accountant → Contador`, `salesperson → Vendedor`,
  `viewer → Visualizador`.

### Frontend — form-error defaults wrapped

- Audit `apps/web/src/routes/**/*.tsx` and feature forms for zod
  schemas that surface a default English message. Either:
  - Pass per-field Spanish messages on the schema (preferred), e.g.
    `z.string().min(1, { message: 'Obligatorio' })`, OR
  - Configure a global zod error map (`z.setErrorMap(spanishErrorMap)`)
    that translates the default codes (`required`, `too_small`,
    `invalid_type`, etc.) to Spanish.
- For `/tenants/new` step 3 specifically: confirm the per-field error
  on `authorization_dgi.number` reads `Obligatorio` instead of
  `Required`. (Step 3's "Opcional" UX issue is owned by G10 — F-009.)

### Tests

- Frontend Vitest: `roleLabel('owner') === 'Propietario'`, etc.
- Frontend integration: render the `/tenants` empresa list — assert
  the role text under each card is the Spanish label, not the raw
  role.
- Frontend integration: render `/tenants/new` step 3 with blank fields
  → click Continuar → assert the alert text is Spanish.

## Non-goals

- Fixing the "Opcional but required" semantics of step 3 (F-009 owned
  by G10).
- Adding new roles or changing role-RBAC. The label map is presentation-only.
- Localizing error text on auth endpoints (already Spanish via the
  problem-code registry).
