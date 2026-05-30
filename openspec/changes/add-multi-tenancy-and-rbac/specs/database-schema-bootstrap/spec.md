## ADDED Requirements

### Requirement: Migration 0003 expands `tenants` with fiscal metadata

Alembic migration `0003_tenants_and_rbac` SHALL have
`down_revision = "0002_identity"` and SHALL ALTER `tenants` to add
`ruc TEXT UNIQUE NOT NULL`,
`regime TEXT NOT NULL CHECK (regime IN ('general','simplified'))`,
`municipality TEXT NOT NULL`,
`authorization_dgi_number TEXT`,
`authorization_dgi_valid_from DATE`,
`authorization_dgi_valid_to DATE`,
`fiscal_address TEXT NOT NULL`,
`is_withholder BOOLEAN NOT NULL DEFAULT FALSE`,
`status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('provisioning','active','suspended','purged'))`,
`updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. The `id`,
`name`, and `created_at` columns from 0001 SHALL remain unchanged.
`tenants` SHALL NOT carry RLS (it is a global catalog per
[ADR-0002](../../../../docs/adr/0002-postgres-rls.md)).

#### Scenario: Tenants table has the expanded columns post-upgrade

- **WHEN** `alembic upgrade head` is run against the 0002 schema
- **THEN** `\d tenants` SHALL list `id`, `name`, `ruc`, `regime`,
  `municipality`, `authorization_dgi_number`,
  `authorization_dgi_valid_from`, `authorization_dgi_valid_to`,
  `fiscal_address`, `is_withholder`, `status`, `created_at`,
  `updated_at`

### Requirement: Migration 0003 creates `tenant_members` with the special policy

The `tenant_members` table SHALL be created with columns
`id UUID PRIMARY KEY`,
`user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`,
`tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`,
`role TEXT NOT NULL CHECK (role IN ('owner','admin','accountant','salesperson','viewer'))`,
`status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','removed'))`,
`joined_at TIMESTAMPTZ NOT NULL DEFAULT now()`,
`removed_at TIMESTAMPTZ`,
`UNIQUE (user_id, tenant_id)`. RLS SHALL be ENABLED and FORCED.
The policy SHALL be:

```sql
CREATE POLICY tenant_members_self ON tenant_members
  USING      (user_id   = current_setting('app.current_user_id', true)::uuid
              OR tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

A partial unique index SHALL enforce single-owner-per-tenant:

```sql
CREATE UNIQUE INDEX uq_tenant_members_owner
  ON tenant_members(tenant_id) WHERE role='owner' AND status='active';
```

#### Scenario: Single-owner constraint blocks a second active owner

- **GIVEN** a tenant `T` with an active owner
- **WHEN** a second `INSERT INTO tenant_members(tenant_id=T, role='owner', status='active', ...)`
  is attempted
- **THEN** the insert SHALL fail with a unique violation

### Requirement: Migration 0003 creates `invitations` with canonical RLS

The `invitations` table SHALL have columns
`id UUID PRIMARY KEY`,
`tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`,
`email CITEXT NOT NULL`,
`proposed_role TEXT NOT NULL CHECK (proposed_role IN ('admin','accountant','salesperson','viewer'))`,
`token_hash TEXT NOT NULL UNIQUE`,
`expires_at TIMESTAMPTZ NOT NULL`,
`status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','cancelled','expired'))`,
`cancelled_at TIMESTAMPTZ`,
`created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. RLS SHALL be
ENABLED and FORCED with the canonical policy:

```sql
CREATE POLICY tenant_isolation ON invitations
  USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

#### Scenario: Cross-tenant read returns zero rows

- **GIVEN** invitations for tenants A and B
- **WHEN** a session with `app.tenant_id=<A>` runs `SELECT * FROM
  invitations`
- **THEN** the result SHALL contain only A's rows

### Requirement: Migration 0003 creates `permissions` and `role_permissions`

The two tables SHALL be created globally without RLS:

```sql
CREATE TABLE permissions (
  code         TEXT PRIMARY KEY,
  resource     TEXT NOT NULL,
  action       TEXT NOT NULL,
  scope        TEXT NOT NULL CHECK (scope IN ('own','all','na')),
  description  TEXT NOT NULL
);

CREATE TABLE role_permissions (
  role        TEXT NOT NULL CHECK (role IN ('viewer','salesperson','accountant','admin','owner')),
  permission  TEXT NOT NULL REFERENCES permissions(code) ON DELETE RESTRICT,
  PRIMARY KEY (role, permission)
);
```

#### Scenario: Tables exist after upgrade

- **WHEN** `alembic upgrade head` is run
- **THEN** `permissions` and `role_permissions` SHALL exist with the
  declared columns and constraints

### Requirement: Migration 0003 seeds permissions from the Python catalog

The migration SHALL import `shared_kernel.permissions.catalog`,
read `TENANT_PERMISSIONS` and `DEFAULT_ROLE_PERMISSIONS`, and
issue `INSERT ... ON CONFLICT DO NOTHING` for each row. After
upgrade the database SHALL contain exactly the six `tenant:*` /
`members:*` rows in `permissions` and the corresponding
`(role, code)` pairs in `role_permissions` as declared in
`DEFAULT_ROLE_PERMISSIONS`. The migration SHALL log the inserted
counts:

```
[migration 0003] permissions seeded: 6
[migration 0003] role_permissions seeded: 22
```

Sprints 04-08 will extend the catalog and add to the seed via
their own migrations using the same `ON CONFLICT DO NOTHING`
pattern.

#### Scenario: Seed matches catalog after upgrade

- **WHEN** the migration completes
- **THEN** `SELECT code FROM permissions ORDER BY code` SHALL equal
  the sorted list of `p.code for p in TENANT_PERMISSIONS`

### Requirement: Migration 0003 is reversible

`downgrade()` SHALL drop `role_permissions`, then `permissions`,
then the partial unique owner index, then `invitations`, then
`tenant_members`, then remove the columns added to `tenants`. The
`tenants` rows present at the time of downgrade SHALL retain `id`,
`name`, `created_at` from the 0002 state.

#### Scenario: Round-trip leaves no residue

- **WHEN** `alembic upgrade head` then `alembic downgrade -1` is
  run
- **THEN** `\d tenants` SHALL list only the post-0002 columns and
  `tenant_members`, `invitations`, `permissions`,
  `role_permissions` SHALL NOT exist
