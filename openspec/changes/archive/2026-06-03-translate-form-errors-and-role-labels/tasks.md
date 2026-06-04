## 1. Shared role-label helper

- [x] 1.1 `apps/web/src/features/tenants/lib/role-labels.ts` ships `ROLE_LABELS` and `roleLabel(role)` covering all five roles: `owner → Propietario`, `admin → Administrador`, `accountant → Contador`, `salesperson → Vendedor`, `viewer → Visualizador`.
- [x] 1.2 `InvitationsTable.tsx` imports `ROLE_LABELS` from the shared helper.
- [x] 1.3 `app-sidebar/tenant-switcher.tsx` switched from its inline `ROLE_TRANSLATIONS` map to `roleLabel(role)`.
- [x] 1.4 `routes/tenants/index.tsx` empresa-card Badge renders `roleLabel(membership.role)` instead of the raw role string. The badge no longer carries `capitalize` (the labels are already correctly cased).

## 2. Spanish zod error map

- [x] 2.1 `apps/web/src/lib/zod-spanish-error-map.ts` exports `spanishErrorMap` covering `invalid_type`, `too_small`, `too_big`, `invalid_string`, `invalid_enum_value`, and `custom` issue codes.
- [x] 2.2 Registered once at bootstrap via `z.setErrorMap(spanishErrorMap)` in `apps/web/src/main.tsx`.

## 3. Step-3 specific copy

- [ ] 3.1 Explicit `{message:'Obligatorio'}` on `authorization_dgi.number` — deferred to change #12 (`fix-wizard-optional-step-and-state-regression`), which owns the wizard step-3 schema rewrite.
- [ ] 3.2 Browser smoke — deferred.

## 4. Tests

- [x] 4.1 `apps/web/tests/unit/features/tenants/role-labels.test.ts` covers all five roles + the fallback.
- [x] 4.2 Existing integration tests (`MembersTable.spec.tsx`, `empresa/users.spec.tsx`) updated to assert `Visualizador` (was `Lector`); pass.
- [ ] 4.3 Wizard Vitest "no English appears" — deferred with #3.

## 5. Validation

- [x] 5.1 `openspec validate translate-form-errors-and-role-labels --strict` exits 0.
