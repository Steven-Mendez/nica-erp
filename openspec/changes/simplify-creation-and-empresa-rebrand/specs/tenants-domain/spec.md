## ADDED Requirements

### Requirement: Tenant aggregate accepts Optional fiscal value objects

The Tenant domain aggregate SHALL accept Optional values
for ruc, regime, municipality, authorization_dgi, and
fiscal_address. The constructor and the register factory
MUST treat each of these fields as `Optional[...]`. A
tenant constructed with `None` for any of those fields
MUST be considered a valid aggregate instance — the
aggregate represents the business reality that the
operator may not have provided that data yet.

The value objects themselves (`Ruc`, `Regime`,
`Municipality`, `AuthorizationDgi`) MUST remain strict —
their constructors continue to raise `ValueError` on a
malformed input. The Optional gating happens at the
aggregate boundary: if a caller supplies a value, it MUST
be wrapped in the corresponding VO; if absent, the
aggregate stores `None`.

#### Scenario: Aggregate constructs with only `name`

- **WHEN** `Tenant.register(name="Mi Empresa", ruc=None,
  regime=None, municipality=None, authorization_dgi=None,
  fiscal_address=None, is_withholder=False, now=...)` is
  called
- **THEN** the returned aggregate has `.name == "Mi
  Empresa"`, `.ruc is None`, `.regime is None`, and so on;
  no exception is raised

#### Scenario: Mixing provided and absent fields

- **WHEN** `Tenant.register(name="Mi Empresa",
  ruc=Ruc.parse("0010101800010X"), regime=None, ...)` is
  called
- **THEN** the aggregate has `.ruc == Ruc(...)` and
  `.regime is None`; partial state is valid

#### Scenario: Malformed value still rejected at the VO

- **WHEN** the caller attempts `Ruc.parse("not-a-ruc")`
- **THEN** `Ruc.__post_init__` raises `ValueError`
  unchanged; the Optional pattern does NOT loosen the VO

### Requirement: Repository round-trips NULL fiscal columns

The `tenant_repository._load` SHALL construct each Optional
VO conditionally:
```
ruc=Ruc(row["ruc"]) if row["ruc"] is not None else None
regime=Regime(row["regime"]) if row["regime"] is not None else None
...
```
The repository `add` / `update` paths SHALL pass `None` to
the SQL bind when the aggregate's field is `None`, relying
on the existing nullable column definitions in migration
`0003_tenants_and_rbac.py`.

#### Scenario: NULL columns round-trip to None aggregates

- **WHEN** a tenant row exists in the DB with `ruc IS
  NULL`, `regime IS NULL`, etc., and the repository's
  `get(id)` is called
- **THEN** the returned `Tenant` aggregate has `.ruc is
  None`, `.regime is None`, etc.

#### Scenario: Multiple tenants with NULL RUC do not violate `uq_tenants_ruc`

- **WHEN** two tenants are created via the use case, each
  with `ruc=None`
- **THEN** both inserts succeed (Postgres treats multiple
  NULL values as distinct under a UNIQUE constraint)
