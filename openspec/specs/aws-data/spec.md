# aws-data Specification

## Purpose
TBD - created by archiving change add-aws-runtime-stack. Update Purpose after archive.
## Requirements
### Requirement: RDS PostgreSQL 17 single-AZ on db.t4g.micro

The `infra/terraform/modules/data/` module SHALL create one
`aws_db_instance` named `nica-erp-demo` with `engine="postgres"`,
`engine_version="17"`, `instance_class="db.t4g.micro"`,
`allocated_storage=20`, `storage_type="gp3"`, `multi_az=false`,
`publicly_accessible=false`, attached to the private subnets and
the `sg_rds` security group emitted by the network module. The
instance SHALL carry the tag `Project=nica-erp`.

#### Scenario: RDS instance has the expected shape

- **WHEN** `aws rds describe-db-instances --db-instance-identifier nica-erp-demo`
  is called after apply
- **THEN** the response SHALL show `Engine=postgres`,
  `EngineVersion` starting with `17.`, `DBInstanceClass=db.t4g.micro`,
  `AllocatedStorage=20`, `StorageType=gp3`, `MultiAZ=false`,
  `PubliclyAccessible=false`

### Requirement: Pre-launch destruction posture

The RDS instance SHALL set `skip_final_snapshot=true`,
`deletion_protection=false`, `backup_retention_period=0`,
`performance_insights_enabled=false`. The module SHALL declare
input variables `enable_rds_proxy` (default `false`) and
`enable_read_replica` (default `false`); neither resource SHALL be
created at the default values.

#### Scenario: Backups are disabled

- **WHEN** the RDS instance is described after apply with default
  module inputs
- **THEN** `BackupRetentionPeriod` SHALL equal `0` and
  `DeletionProtection` SHALL equal `false`

#### Scenario: Destroy is unblocked

- **WHEN** `terraform destroy` runs against the demo environment
- **THEN** the RDS instance SHALL be destroyed in under 15 minutes
  without a manual final-snapshot prompt

### Requirement: Credentials generated in the data module, persisted only via the secrets module

The module SHALL generate the master username (`nica_erp_demo`) and
a random 32-character password via `random_password`. The credentials
SHALL be exposed as `sensitive = true` Terraform outputs
(`rds_username`, `rds_password`, `rds_database_name`,
`rds_endpoint`, `rds_port`) consumed exclusively by the
`infra/terraform/modules/secrets/` module, which is the SOLE writer
of the SSM SecureString parameters
`/nica-erp/demo/rds/url`, `/nica-erp/demo/rds/username`, and
`/nica-erp/demo/rds/password` (see `aws-secrets`). The `envs/demo`
root SHALL NOT re-export any password output at the env level —
there SHALL be no non-secrets path through which the password
reaches stdout, the state file in plaintext, or any non-SecureString
parameter.

#### Scenario: Password is not an env-level output

- **WHEN** `terraform -chdir=infra/terraform/envs/demo output -json`
  is invoked after apply
- **THEN** the JSON response SHALL NOT contain a key whose value
  matches the random password

#### Scenario: SSM parameters are SecureString

- **WHEN** `aws ssm describe-parameters --filters Key=Name,Values=/nica-erp/demo/rds/`
  is called after apply
- **THEN** the three `/nica-erp/demo/rds/*` parameters SHALL each
  have `Type=SecureString`, written by the `secrets` module

