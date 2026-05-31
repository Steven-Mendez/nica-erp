# Fix tenant id race on refresh

## Why
Refrescar `/empresa/users` (y rutas similares) dispara `GET /v1/tenants//members`
y `/v1/tenants//invitations` (doble slash → 404) porque las queries del feature
`tenants` se ejecutan con `tenantId = ""` mientras `useMeQuery` aún no resuelve
`active_tenant`. Cuando `me.data` llega, las queries se re-ejecutan con el UUID
correcto, así que la UI funciona, pero cada refresh deja dos requests 404 en el
log del API.

## Definition of done
- Las queries del feature `tenants` (`useTenantQuery`, `useMembersQuery`,
  `useInvitationsQuery`) no disparan con tenantId vacío.
- Refrescar `/empresa/users` y `/empresa` no produce 404s en el log del API.
- `pnpm typecheck` y `pnpm lint` en `apps/web/` quedan limpios.

## Tasks
- [x] 1. Gatear `useTenantQuery`, `useMembersQuery`, `useInvitationsQuery` con `enabled: Boolean(tenantId)` en `apps/web/src/features/tenants/api/hooks.ts`.
- [x] 2. Verificar typecheck + lint en `apps/web/`.

## Notes
- 1. `apps/web/src/features/tenants/api/hooks.ts:53-72`: añadido `enabled: tenantId !== ""` a las tres queries del feature.
- 2. `pnpm typecheck` y `pnpm lint` limpios; los 40 unit tests del feature `tenants` pasan.

## Summary
Causa raíz: `useTenantQuery` / `useMembersQuery` / `useInvitationsQuery` corrían
con `tenantId = ""` mientras `useMeQuery` aún resolvía, generando requests
`/v1/tenants//…` (doble slash → 404) en cada refresh. Fix: gatear los tres
hooks con `enabled: tenantId !== ""`. Sin cambios en call sites; typecheck +
lint + unit tests verdes.
