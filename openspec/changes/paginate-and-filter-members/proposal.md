## Why

`GET /v1/tenants/{tenant_id}/members` returns the entire member roster
for the tenant in a single unbounded `list[MemberResponse]`. At sprint 03
scale (a handful of members per tenant) this is invisible, but the shape
of the contract guarantees the cost grows linearly in member count
forever:

- The Python loop over members fanned out into one `users.get_by_id`
  query per row (sprint 03's first N+1; fixed in the pre-Tier 3 work
  via `users.list_by_ids`).
- Every row, every column, every page lands in the browser, where the
  table renders client-side filtering, sorting, and pagination via
  TanStack Table. Typing `j` in the search box re-walks the entire
  array; switching pages does nothing on the wire.
- The SPA already round-trips filter + sort + pagination through URL
  search params (`q`, `roles`, `statuses`, `sort`, `dir`, `page`,
  `size`) as of the Tier 2 work — but the backend ignores them.

This change moves the work back to the database: the endpoint accepts
the same parameter set the SPA already encodes, applies them as WHERE +
ORDER BY + LIMIT/OFFSET against an indexed `tenant_members` (the index
landed in migration `0005_tenant_members_lookup_index`), and returns a
paginated envelope. The frontend switches TanStack Table to
`manualPagination` / `manualFiltering` / `manualSorting` so the table
becomes a thin view layer over the API response instead of a parallel
implementation.

References:
[`docs/sprints/README.md` — DoD](../../../docs/sprints/README.md),
[ADR-0001](../../../docs/adr/0001-hexagonal-architecture.md),
[ADR-0009](../../../docs/adr/0009-rest-style-api.md) (if present),
goal `.claude/goals/optimize-users-table-filters.md`.

## What Changes

### Endpoint contract

`GET /v1/tenants/{tenant_id}/members` SHALL accept the following query
parameters, all optional:

| Parameter   | Type / values                                                                 | Default      |
|-------------|-------------------------------------------------------------------------------|--------------|
| `limit`     | int, `1..100`                                                                 | `25`         |
| `offset`    | int, `>=0`                                                                    | `0`          |
| `q`         | free-text, max 200 chars; case-insensitive substring against display_name + email + user_id | (no filter)  |
| `roles`     | repeated enum: `owner|admin|accountant|salesperson|viewer`                    | (all roles)  |
| `statuses`  | repeated enum: `active|removed`                                               | (all)        |
| `sort`      | enum: `joined_at|display_name|email|role`                                     | `joined_at`  |
| `dir`       | enum: `asc|desc`                                                              | `asc`        |

The response body SHALL change from `list[MemberResponse]` to:

```json
{
  "items": [ /* MemberResponse[] */ ],
  "total": <int — filtered count, ignoring limit/offset>,
  "limit": <int — echoed>,
  "offset": <int — echoed>
}
```

This is a breaking response-shape change for a single in-repo caller
(the SPA). No external client consumes the endpoint; `pnpm gen:api`
regenerates the typed client in the same PR so the change is atomic.

### Backend

- New value object `ListMembersQuery(tenant_id, q?, roles?, statuses?,
  sort, dir, limit, offset)` under `contexts.tenants.application.use_cases`.
- `ListMembers.execute(query: ListMembersQuery) -> ListMembersResult`
  returns `(items: list[MemberView], total: int)`.
- `MembershipRepository` port gains
  `list_page(query: ListMembersQuery) -> (rows, total)`. The SqlAlchemy
  adapter implements it as a single `SELECT ... JOIN users ... WHERE ...
  ORDER BY ... LIMIT ... OFFSET ...` plus a `SELECT COUNT(*) ... WHERE
  ...`. The existing `list_by_tenant` stays for callers that need every
  row (none today; mark for removal once verified).
- The HTTP router fetches enriched rows directly from the JOIN — no
  more cross-context `UserRepository.list_by_ids` step at this site.
- The Tier 1 index `ix_tenant_members_tenant_id_joined_at` covers the
  default sort path; sorts on `display_name | email | role` accept a
  seq-scan-then-sort for the MVP (under 1k rows per tenant assumed).
  Document this in `design.md`.

### Frontend

- `listMembers(tenantId, params)` accepts the parameter set above and
  returns the new envelope. The TS signature derives from
  `schema.d.ts` after `pnpm gen:api`.
- `useMembersQuery({ tenantId, params })` keyed by
  `["tenant", id, "members", params]` so each filter/page combination
  caches independently; `placeholderData: keepPreviousData` continues
  to hide refetch flashes between pages.
- `EmpresaUsuariosRoute` already owns URL state — it forwards the
  derived params straight to `useMembersQuery` and to TanStack Table.
- `MembersTable` opts into `manualPagination`, `manualFiltering`,
  `manualSorting`, drops `getFilteredRowModel` /
  `getPaginationRowModel` / `getSortedRowModel`, and reads `total` for
  the pagination footer. The client-side `globalFilterFn` and column
  `filterFn` callbacks become inert / removed.
- Total / page-count UI is computed from `total` + `limit` instead of
  `getFilteredRowModel().rows.length`.

### Tests

- Repository integration test seeds 30 members across roles/statuses,
  asserts (a) one round-trip for the page query, one for the count,
  (b) `q` matches case-insensitively across the three fields,
  (c) each sort direction stable for `joined_at`, (d) `limit`+`offset`
  return the correct slice.
- Use-case unit test covers parameter validation (e.g. `limit > 100`
  → domain error).
- HTTP router integration test seeds members, asserts the envelope
  shape and that defaults round-trip.
- FE: `useMembersQuery` test verifies queryKey includes params and
  the call passes them through. `MembersTable` test pins the manual-mode
  contract (total comes from props, pageCount uses `Math.ceil(total /
  limit)`).
