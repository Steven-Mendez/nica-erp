# Optimize Users Table Filters

## Why

Route `/empresa/users` feels fast today but a quick audit found real
under-the-hood debt that will bite as tenants grow:

- **N+1 query** in `GET /v1/tenants/{tenant_id}/members`: for every member row
  the handler issues a separate `user_repo.get_by_id(user_id)` call.
- **No DB index** for the `WHERE tenant_id = ?` filter on `tenant_members`
  (the only multi-column index leads with `user_id`, so it's not usable).
- **Unbounded API**: endpoint returns *all* members with no pagination, no
  filtering, no sorting parameters.
- **Frontend filters all client-side** with no debounce, no URL state, and no
  `placeholderData` — every keystroke re-filters the full set and tenant
  switches blank the table.

Table does use TanStack Table + TanStack Query (confirmed). The plumbing is
right; the optimizations are missing.

## Definition of done

- N+1 in `list_members` replaced with a single batched user lookup; covered
  by an integration test that asserts ≤ 2 DB round-trips.
- Composite index `(tenant_id, joined_at)` exists on `tenant_members` via a
  new Alembic migration; `make migrate && make migrate-down && make migrate`
  clean.
- Global search input on `MembersTable` debounced (~300ms) so typing doesn't
  re-render on every keystroke.
- React Query hook for members uses `placeholderData: keepPreviousData` so
  tenant switches don't blank the table.
- Filters + pagination state synced to URL search params via TanStack Router
  so refresh/back-button preserves view.
- (Tier 3, optional) Server-side pagination + filter params on the API,
  client passes them through, schema regenerated. Decide after Tier 1 lands.
- `pytest -m unit`, `pytest -m integration`, `pnpm typecheck`, `pnpm lint
  --max-warnings=0`, `pnpm test --run` all green.

## Tasks

### Tier 1 — quick wins (no API contract change)
- [x] 1. Fix N+1 in `list_members` HTTP handler — batch user fetch via a new
        `user_repo.list_by_ids(ids)` method; add integration test.
- [x] 2. Add Alembic migration creating index
        `ix_tenant_members_tenant_id_joined_at` on `(tenant_id, joined_at)`.
- [x] 3. Add debounced global search to `MembersTable` (existing
        `useDebouncedValue` if present, else inline).
- [x] 4. Add `placeholderData: keepPreviousData` to `useMembersQuery` (and
        `useInvitationsQuery` if same shape).

### Tier 2 — URL state sync (FE-only)
- [x] 5. Sync `MembersTable` filters + pagination + sort to TanStack Router
        search params on `/empresa/users` so the view is shareable and
        survives refresh.

### Tier 3 — server-side pagination + filters (decide after Tier 1)
- [x] 6. Decide: do we need server-side pagination/filter API now, or defer?
        Decision (user-chosen): implement now under
        OpenSpec change `paginate-and-filter-members`.

## Notes
- Tier 1: N+1 fix in `list_members` HTTP handler — added
  `UserRepository.list_by_ids` port + SqlAlchemy adapter; HTTP handler
  now does one batched user fetch instead of one per row.
- Tier 1: Alembic 0005 created
  `ix_tenant_members_tenant_id_joined_at` on `(tenant_id, joined_at)`.
- Tier 1: 250ms debounce on the MembersTable global search via new
  `useDebouncedValue` hook (`apps/web/src/lib/`).
- Tier 1: `placeholderData: keepPreviousData` on `useMembersQuery` +
  `useInvitationsQuery`.
- Tier 2: `/empresa/users` search-param schema (`tab`, `q`, `roles`,
  `statuses`, `sort`, `dir`, `page`, `size`) round-trips with
  TanStack Router's `useSearch` / `useNavigate`. `MembersTable`
  refactored to accept an optional controlled `viewState` /
  `onViewStateChange` so the route owns the URL <-> table bridge
  without breaking the existing internal-state callers.
- Tier 3: OpenSpec change `paginate-and-filter-members` drafted +
  validated. Endpoint contract changed:
  `GET /v1/tenants/{tenant_id}/members` now accepts
  `limit`/`offset`/`q`/`roles`/`statuses`/`sort`/`dir` and returns
  `{ items, total, limit, offset }`. Repository gained `list_page`
  via SQL JOIN against `users` (no more cross-context N+1 enrichment
  at HTTP). Frontend switched TanStack Table to
  `manualPagination`/`manualFiltering`/`manualSorting`, queryKey
  includes the params, `useMembersQuery` accepts a `ListMembersParams`
  arg, and `MembersTable.total` drives `rowCount`/`pageCount`.
- Final test counts: 298 backend (unit+integration), 288 frontend.
  Lint + typecheck clean on both.
- Mid-session note: a parallel commit (`a9652cd` feat(onboarding)
  bundled onboarding work + my Tier 1.4 hooks.ts edit) appeared
  between turns. No data lost; surface noted for future awareness.
