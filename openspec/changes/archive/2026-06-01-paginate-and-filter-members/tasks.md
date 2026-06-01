## 1. Domain + application

- [x] 1.1 New value object
      `contexts.tenants.application.use_cases.list_members.ListMembersQuery`
      with fields `(tenant_id, q, roles, statuses, sort, dir, limit,
      offset)`. Defaults: `sort="joined_at"`, `dir="asc"`,
      `limit=25`, `offset=0`. Validation: `1 <= limit <= 100`,
      `offset >= 0`, `len(q) <= 200`.
- [x] 1.2 New result VO `ListMembersResult(items: list[Membership],
      total: int)`.
- [x] 1.3 Update `ListMembers.execute(query)` to accept the VO and
      return `ListMembersResult`. Old positional signature gone.
- [x] 1.4 Unit test for the use case: happy path delegates to the
      repository; param validation surfaces as a `ValueError` /
      domain error.

## 2. Persistence

- [x] 2.1 `MembershipRepository` port (Protocol) gains
      `list_page(query: ListMembersQuery) -> tuple[Sequence[Membership],
      int]`. Existing `list_by_tenant` stays for now (no consumer
      changes), marked as `# deprecated: prefer list_page`.
- [x] 2.2 SqlAlchemy adapter `MembershipRepositorySqlAlchemy.list_page`
      builds the parameterised SQL via `sqlalchemy.text` + bound
      parameters. The base SELECT joins `tenant_members` LEFT JOIN
      `users` on `user_id` and returns
      `(id, user_id, tenant_id, role, status, joined_at, removed_at,
      display_name, email)` so HTTP no longer needs the
      `UserRepository.list_by_ids` round-trip at this site.
- [x] 2.3 `q` is applied as a single OR predicate:
      `LOWER(users.display_name) LIKE :needle
       OR LOWER(users.email) LIKE :needle
       OR LOWER(tenant_members.user_id::text) LIKE :needle`
      with `:needle = f"%{q.lower()}%"`. ILIKE is acceptable; the
      adapter is responsible for escaping `%` and `_` if present
      in user input.
- [x] 2.4 Sort whitelist enforced in adapter (never interpolate
      user input directly). `joined_at|display_name|email|role`
      → physical columns; `dir` → `ASC|DESC`. Default sort is
      `joined_at ASC` with `user_id` as a tiebreaker to keep
      pagination deterministic.
- [x] 2.5 The COUNT query applies the same WHERE predicate (no
      LIMIT/OFFSET/JOIN-for-sort), reads `COUNT(*)` from the same
      `tenant_members LEFT JOIN users` shape, and returns the
      filtered total.
- [x] 2.6 Integration test
      `tests/integration/contexts/tenants/test_membership_repository.py`
      adds: seeded 30 members, asserts `q` matches across the three
      fields, each sort direction is stable for `joined_at`, and
      `limit`+`offset` returns the expected slice. Assert one
      page-query + one count-query at most (no N+1).

## 3. HTTP adapter

- [x] 3.1 `MembersPageResponse` Pydantic schema:
      `{ items: list[MemberResponse], total: int, limit: int, offset: int }`.
- [x] 3.2 Router `list_members` accepts `Query` params: `limit=25`,
      `offset=0`, `q: str | None = None`, `roles: list[Role] | None
      = Query(default=None)`, `statuses: list[Status] | None`,
      `sort: SortField = "joined_at"`, `dir: SortDir = "asc"`.
      Builds `ListMembersQuery`, awaits the use case, returns
      `MembersPageResponse`. The `UserRepository.list_by_ids` call
      goes away — enrichment is part of the JOIN now.
- [x] 3.3 Update
      `tests/integration/contexts/tenants/http/test_tenants_router.py`
      `test_get_members_returns_list_with_permission`: assert the
      new envelope shape; drop the `list_by_ids` monkeypatch and
      replace it with a `_StubListMembers` that returns a
      `ListMembersResult`.
- [x] 3.4 Add a router test for: defaults round-trip, `limit > 100`
      returns `422`, `q` shorter than 200 chars accepted.

## 4. OpenAPI + types

- [x] 4.1 `make api` boots, `GET /openapi.json` validates.
- [x] 4.2 `cd apps/web && pnpm gen:api`; commit the regenerated
      `apps/web/src/api/schema.d.ts`.

## 5. Frontend endpoints + hooks

- [x] 5.1 `apps/web/src/features/tenants/api/endpoints.ts`:
      `listMembers(tenantId, params)` returns the new envelope; type
      `Member` is unchanged but new `MembersPage` shape exported.
- [x] 5.2 `apps/web/src/features/tenants/api/hooks.ts`:
      `useMembersQuery({ tenantId, params })` keyed by
      `["tenant", id, "members", params]`. `placeholderData:
      keepPreviousData` carried over. Mutations
      (`useRemoveMemberMutation`, `useUpdateMemberRoleMutation`)
      invalidate the broader `["tenant", id, "members"]` prefix so
      every paged cache entry refetches.

## 6. Frontend route + table

- [x] 6.1 `apps/web/src/routes/empresa/users.tsx` derives a
      `params` object from `search` (the existing URL state) and
      passes it to `useMembersQuery`. URL state is already the
      source of truth — no new state ownership.
- [x] 6.2 `MembersTable` accepts `total` (number) and switches the
      `useReactTable` config: `manualPagination: true`,
      `manualFiltering: true`, `manualSorting: true`,
      `rowCount: total`, `pageCount: Math.max(Math.ceil(total /
      pageSize), 1)`. Drop the now-unused
      `getFilteredRowModel`, `getSortedRowModel`,
      `getPaginationRowModel`, `getFacetedRowModel`,
      `getFacetedUniqueValues`. Drop the client `globalFilterFn`
      and column `filterFn` callbacks.
- [x] 6.3 The "Limpiar" button still resets the in-component view
      state but now the change propagates up to the route, which
      writes URL params, which re-runs the query.
- [x] 6.4 The result counter (`{n} resultado(s)`) reads from
      `total` instead of `table.getFilteredRowModel().rows.length`.
- [x] 6.5 Update tests:
      - `MembersTable.spec.tsx` adopts the new `total` prop and
        adjusts the search-box test to assert the table fires a
        view-state change with the debounced `globalFilter` (since
        filtering is no longer applied client-side).
      - `users.spec.tsx` (route) asserts `useMembersQuery` is
        called with the params derived from URL state.

## 7. Definition of done

- [x] 7.1 `pytest -m "unit or integration"` exit 0.
- [x] 7.2 `pnpm typecheck`, `pnpm lint --max-warnings=0`,
      `pnpm test --run` exit 0.
- [x] 7.3 `make migrate && make migrate-down && make migrate` clean
      (migration `0005` already merged; no new migration in this
      change).
- [x] 7.4 `scripts/smoke-api.sh` exit 0; SPA reload at
      `/empresa/users?q=ad&roles=admin&page=2&size=10` round-trips
      params correctly.
