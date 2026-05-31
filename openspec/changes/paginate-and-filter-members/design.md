## Why a single change instead of split

The proposal touches one capability (`tenants-http`) end-to-end:
domain VO, repository SQL, HTTP shape, OpenAPI, FE client, FE table.
Splitting it would land an unused VO and a parameter-accepting repo
without a caller, then a second PR that flips both consumers. Keeping
them in one change keeps the spec coherent and the rollback story
simple — revert one commit.

## Why the URL parameter set matches the table dimensions exactly

`q`, `roles`, `statuses`, `sort`, `dir`, `limit`, `offset` are the
seven dimensions TanStack Table already controls. Naming them
identically on the wire and in the URL means:

- `EmpresaUsersSearch` (zod schema) → `ListMembersParams` (TS type
  from `schema.d.ts`) is a one-line `pick` away.
- The URL `?q=ada&roles=admin,viewer&page=2` reads as the same English
  as the query string the SPA fetches.
- A pasted/bookmarked URL produces the exact same query against the
  database — no client-side post-processing of the API response.

## Why ILIKE instead of full-text search

The MVP tenant size is under 1000 members. ILIKE on
`(display_name, email, user_id)` with an index on
`(tenant_id, joined_at)` and a max page size of 100 stays under 10ms
even with a seq-scan inside the filtered slice. Postgres `pg_trgm` /
`tsvector` would be premature; revisit when a single tenant crosses
~10k members (sprint 09 cost audit will surface the row count).

## Why no `total_pages` in the response envelope

`total` + the echoed `limit` lets the client compute pages exactly.
`pageCount = Math.ceil(total / limit)` is a one-liner; encoding it
in the envelope means the server must commit to a particular
pagination model. Leaving it client-side keeps the contract minimal.

## Why mutations invalidate the broader query prefix

Removing a member from page 7 changes the totals on pages 1, 6, 7,
and 8. Invalidating `["tenant", id, "members"]` (no params suffix)
refetches every active page cache; with `placeholderData:
keepPreviousData` the user sees the prior data until the new pages
arrive. Surgical per-page invalidation would force the FE to model
the cascade — not worth the complexity at this size.

## Why we keep `list_by_tenant` in the repo for now

Future internal callers (e.g. background sync to a search index, or
the seamless onboarding flow that needs every member in one shot)
may need an unbounded list. Marking it deprecated lets us notice
when someone adds a new caller, without churning the repo surface
twice in this change.

## Why sorts on `display_name | email | role` are seq-scan-tolerated

Those sorts pivot on `users.display_name`, `users.email`, and
`tenant_members.role`. Adding indexes for each is straightforward
but each one slows writes and bloats the table. At MVP scale the
sort happens inside the LIMIT slice after the
`tenant_id`-indexed scan, so the sort cost is proportional to the
filtered subset (typically the whole tenant — still cheap). If a
post-pilot tenant grows past a few thousand active members, the
follow-up is to add `(tenant_id, role)` and rely on
`users.display_name` / `users.email` already-existing indexes (or
add them then).
