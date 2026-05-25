## ADDED Requirements

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

### Requirement: Credentials stored only in SSM SecureString

The module SHALL generate the master username (`nica_erp_demo`) and
a random 32-character password via `random_password`. The module
SHALL write three SSM SecureString parameters:
`/nica-erp/demo/rds/url` (full SQLAlchemy URL of the form
`postgresql+asyncpg://<user>:<pass>@<endpoint>:5432/<db>`),
`/nica-erp/demo/rds/username`, `/nica-erp/demo/rds/password`. The
module SHALL NOT emit the password as a Terraform output, nor in
any non-SecureString SSM parameter.

#### Scenario: Password is not a Terraform output

- **WHEN** `terraform output -json` is invoked against the data
  module
- **THEN** the JSON response SHALL NOT contain a key whose value
  matches the random password

#### Scenario: SSM parameters are SecureString

- **WHEN** `aws ssm describe-parameters --filters Key=Name,Values=/nica-erp/demo/rds/`
  is called after apply
- **THEN** the three parameters above SHALL each have
  `Type=SecureString`
