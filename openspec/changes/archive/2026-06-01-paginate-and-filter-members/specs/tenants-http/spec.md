## MODIFIED Requirements

### Requirement: Members list endpoint SHALL accept pagination, filter, and sort parameters and return a paginated envelope

The endpoint `GET /v1/tenants/{tenant_id}/members` SHALL accept the
following query parameters, all optional:

- `limit`: integer in `[1, 100]`, default `25`.
- `offset`: integer `>= 0`, default `0`.
- `q`: string up to 200 characters; case-insensitive substring search
  against `users.display_name`, `users.email`, and the textual form of
  `tenant_members.user_id`.
- `roles`: repeated enum from
  `{owner, admin, accountant, salesperson, viewer}`. Empty / absent
  means "no role filter".
- `statuses`: repeated enum from `{active, removed}`. Empty / absent
  means "no status filter".
- `sort`: enum from `{joined_at, display_name, email, role}`,
  default `joined_at`.
- `dir`: enum from `{asc, desc}`, default `asc`.

A request with `limit > 100`, `limit < 1`, or `offset < 0` SHALL be
rejected with `422 Unprocessable Entity`.

The response body SHALL be a JSON object of shape:

```json
{
  "items": [/* MemberResponse[] */],
  "total": <int>,
  "limit": <int>,
  "offset": <int>
}
```

`items` SHALL contain at most `limit` rows. `total` SHALL be the count
of members matching the filter predicates (`q`, `roles`, `statuses`),
ignoring `limit` and `offset`. `limit` and `offset` SHALL echo the
effective values used to compute `items`.

The endpoint SHALL execute at most one query for the page rows and one
query for the count — no per-row enrichment fan-out is permitted.

#### Scenario: Default request returns first page of 25 sorted by joined_at ascending

- **GIVEN** a tenant with 30 active members spanning all five roles
- **WHEN** the caller invokes `GET /v1/tenants/{id}/members` with no
  query parameters
- **THEN** the response status SHALL be `200`
- **AND** the body SHALL satisfy `items.length == 25`, `total == 30`,
  `limit == 25`, `offset == 0`
- **AND** `items` SHALL be ordered by `joined_at` ascending

#### Scenario: `q` matches across display_name, email, and user_id

- **GIVEN** members include one with `display_name = "Ada Lovelace"`,
  one with `email = "bob@nica.test"`, and one with
  `user_id = "00000000-0000-0000-0000-0000ada000aa"`
- **WHEN** the caller invokes `GET /v1/tenants/{id}/members?q=ada`
- **THEN** `items` SHALL include both the `Ada Lovelace` row and the
  row whose `user_id` contains `ada`, and SHALL NOT include the `bob`
  row, and `total` SHALL equal `2`

#### Scenario: Combined filters narrow the result

- **GIVEN** the tenant has 10 active admins, 5 removed admins, and
  20 active viewers
- **WHEN** the caller invokes
  `GET /v1/tenants/{id}/members?roles=admin&statuses=active`
- **THEN** `total` SHALL equal `10` and every row in `items` SHALL
  satisfy `role == "admin"` and `status == "active"`

#### Scenario: Page beyond the last page returns empty items

- **GIVEN** a tenant with 30 members and `limit=10`
- **WHEN** the caller invokes
  `GET /v1/tenants/{id}/members?limit=10&offset=30`
- **THEN** the response status SHALL be `200`
- **AND** `items.length == 0`, `total == 30`, `limit == 10`,
  `offset == 30`

#### Scenario: `limit > 100` is rejected

- **GIVEN** any authenticated caller with `members:read`
- **WHEN** the caller invokes
  `GET /v1/tenants/{id}/members?limit=101`
- **THEN** the response status SHALL be `422`

#### Scenario: Sort by display_name descending

- **GIVEN** members `("Carla", ...), ("Ana", ...), ("Beto", ...)`
- **WHEN** the caller invokes
  `GET /v1/tenants/{id}/members?sort=display_name&dir=desc`
- **THEN** `items` SHALL be ordered `["Carla", "Beto", "Ana"]`

### Requirement: Members list endpoint SHALL enrich each row with display_name and email in a single query

The endpoint SHALL return `display_name` and `email` for each row by
joining `tenant_members` against `users` on `user_id` inside the SQL
that builds the page, rather than fetching them separately per row or
per page. Rows whose `user_id` has no matching `users` row SHALL
surface `display_name = null` and `email = null` (left join, not
inner join).

#### Scenario: Row whose user was deleted shows null display_name and email

- **GIVEN** a member row whose `user_id` no longer matches any row in
  the `users` table
- **WHEN** that member appears in the response
- **THEN** the row SHALL satisfy `display_name == null` and
  `email == null`
