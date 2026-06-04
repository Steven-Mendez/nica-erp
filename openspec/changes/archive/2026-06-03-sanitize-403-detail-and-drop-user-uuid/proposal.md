## Why

Two information-disclosure cleanups from the audit:

- **F-030** — the 403 envelope for `tenant.required` includes the
  internal claim path:
  `{"detail":"JWT has no 'custom:active_tenant' claim","code":"tenant.required"}`.
  Low risk by itself; pairs poorly with F-011's token-type confusion
  (an attacker forging a JWT learns the exact claim path to inject).
- **F-031** — `/empresa/users` Miembros desktop table renders the
  user UUID (`a9599c14-…`) as plain text next to every member's
  name. The mobile list view does NOT. UUIDs are not secrets but they
  serve no operator purpose; they should not be rendered.

This change replaces the 403 detail with a generic Spanish copy and
removes the UUID column from the members table.

## What Changes

### Backend — generic Spanish 403 detail

- `apps/api/src/contexts/tenants/adapters/inbound/http/errors.py`
  (and equivalent in identity, where the active-tenant check fires):
  the `tenant.required` 403 detail SHALL be the Spanish copy
  `Acceso denegado: empresa no seleccionada.` (no claim path).
- Equivalent generic copy for `missing-permission`: `Acceso denegado:
  faltan permisos.` The `missing:[...]` array (which the audit found
  empty in some paths) SHALL be omitted from the response body
  entirely when empty.

### Frontend — drop UUID column

- `apps/web/src/features/tenants/components/MembersTable.tsx` (or
  wherever the desktop table lives): remove the column that renders
  `member.user_id`. Keep the underlying field in the row data — it
  is still useful for the actions menu (kebab → "Cambiar rol",
  etc.) but it SHALL NOT be rendered as a visible cell.

### Tests

- Backend unit: 403 envelopes have the documented Spanish detail and
  no claim path.
- Backend integration: every cross-tenant probe path returns the new
  detail.
- Frontend Vitest: the members table renders members but does NOT
  render the UUID string as cell text.

## Non-goals

- Generic-ifying every 403 envelope across every context. This change
  scopes to `tenant.required` and `missing-permission` only.
- Hiding the UUID from API responses (it stays in
  `GET /v1/tenants/{id}/members`; the change is presentation-layer
  only).
- Translating other error codes — see G5 for the broader Spanish
  copy initiative.
