## 1. Backend 403 sanitization

- [x] 1.1 `tenant.required` (in `apps/api/src/contexts/identity/adapters/inbound/http/middleware.py`) now emits Spanish title `Acceso denegado` and detail `Acceso denegado: empresa no seleccionada.` — the JWT claim path is gone.
- [x] 1.2 `missing-permission` (in `apps/api/src/contexts/tenants/adapters/inbound/http/errors.py`) emits Spanish title and detail; the `missing` array is omitted when empty.
- [x] 1.3 `tenant.not_member` (same module) emits a generic `Acceso denegado.` Spanish detail and no longer embeds the tenant UUID.

## 2. Frontend members table

- [x] 2.1 `MembersTable.tsx`: the `user_id` UUID line under each member name was removed. `member.user_id` is still on the row data (used by the kebab menu for `removeMember`/`updateMemberRole`).
- [x] 2.2 The actions menu's `aria-label` now uses display_name (then email, then "miembro") instead of the UUID, so screen-reader output also drops the UUID. Mobile card view (no UUID) is unchanged.

## 3. Tests

- [x] 3.1 Backend integration suite for tenants + identity middleware passes — no remaining test asserts the old strings.
- [x] 3.2 Frontend `MembersTable.spec.tsx` updated to use email-based aria-label assertions; the suite passes.

## 4. Validation

- [x] 4.1 `openspec validate sanitize-403-detail-and-drop-user-uuid --strict` exits 0.
