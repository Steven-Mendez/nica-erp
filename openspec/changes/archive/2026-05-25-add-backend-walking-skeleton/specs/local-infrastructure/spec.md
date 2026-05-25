## ADDED Requirements

### Requirement: Docker Compose stack defines Postgres, LocalStack, Mailpit

`docker/docker-compose.yml` SHALL define three services:
- `postgres`: image `postgres:17-alpine`, listening on `5432`, with a
  `pg_isready` healthcheck and a named volume for `/var/lib/postgresql/data`.
- `localstack`: image `localstack/localstack:3.7`, listening on `4566`,
  with `SERVICES=s3,sqs,events,ssm` and `AWS_DEFAULT_REGION=us-east-1`.
- `mailpit`: image `axllent/mailpit:latest`, exposing SMTP on `1025` and
  the web UI on `8025`.
The compose project name SHALL be `nica-erp`.

#### Scenario: `make local-up` brings the three services up
- **WHEN** a developer runs `make local-up` on a clean Docker host
- **THEN** containers `nica-erp-postgres`, `nica-erp-localstack`, and
  `nica-erp-mailpit` SHALL be running

### Requirement: Postgres credentials and database match local defaults

The Postgres container SHALL be initialised with `POSTGRES_USER=nica_erp`,
`POSTGRES_PASSWORD=nica_erp`, and `POSTGRES_DB=nica_erp`. These values
SHALL match the default `DATABASE_URL` /  `ALEMBIC_DATABASE_URL` shipped
in `.env.local.example`.

#### Scenario: Default URLs connect with no config
- **WHEN** a developer copies `.env.local.example` to `.env.local`
  unchanged and runs `make migrate`
- **THEN** Alembic SHALL successfully apply `0001_shared_kernel`

### Requirement: LocalStack init creates AWS resources by name

`docker/localstack-init.sh` SHALL run on container readiness and SHALL
create (best-effort, idempotent): S3 bucket `nica-erp-files`, SQS queues
`notif-queue`, `notif-queue-dlq`, `audit-queue`, `audit-queue-dlq`, and
EventBridge bus `nica-erp`. Every command SHALL tolerate the resource
already existing (`|| true`).

#### Scenario: Re-running the init script is safe
- **WHEN** the LocalStack container restarts and the init script runs
  against an environment where the resources already exist
- **THEN** the script SHALL exit with code 0

### Requirement: Postgres data persists across container restarts

A named Docker volume `pg_data` SHALL back `/var/lib/postgresql/data` so
that stopping and starting the Postgres container preserves database
state.

#### Scenario: Data survives compose restart
- **WHEN** a developer migrates, stops the stack with `make local-down`,
  and brings it back up with `make local-up`
- **THEN** `SELECT version_num FROM alembic_version` SHALL still return
  the latest revision

### Requirement: .env.local.example documents every runtime variable

`.env.local.example` at the repo root SHALL declare the variables the
API reads at startup: `APP_ENV`, `DATABASE_URL`, `ALEMBIC_DATABASE_URL`,
`AWS_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_REGION`, `S3_FILES_BUCKET`, `EVENTBRIDGE_BUS_NAME`,
`SQS_NOTIF_QUEUE_URL`, `SQS_AUDIT_QUEUE_URL`, `SMTP_HOST`, `SMTP_PORT`,
`SMTP_FROM`, `CORS_ALLOWED_ORIGINS`. Values SHALL point at the local
Docker stack.

#### Scenario: Copying the example is enough to boot
- **WHEN** a contributor copies `.env.local.example` to `.env.local`
  verbatim and runs `make local-up && make migrate && make api`
- **THEN** the API SHALL serve `GET /healthz` successfully on `:8000`
