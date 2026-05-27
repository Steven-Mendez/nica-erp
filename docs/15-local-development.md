# 15 — Local Development

Most development happens without AWS. Every port has a local adapter; the swap to AWS happens in `bootstrap/container.py`. Frontend in [09 — Frontend](09-frontend.md).

---

## Topology

```mermaid
flowchart LR
    Dev[Developer]
    subgraph Host
        Web["apps/web<br/>Vite :5173"]
        API["apps/api<br/>uvicorn :8000"]
        Workers["Workers<br/>Python loops"]
        subgraph Docker["docker compose"]
            PG[("Postgres :5432")]
            LS["LocalStack :4566"]
            MP["Mailpit :1025/:8025"]
        end
    end
    Dev --> Web --> API --> PG
    API --> LS
    API --> MP
    Workers --> PG
    Workers --> LS
```

---

## Local stack

`docker/docker-compose.yml`: Postgres 17, LocalStack community (`S3,SQS,events,ssm`), Mailpit. `localstack-init.sh` creates the `nica-erp-files` bucket, queues + DLQs (`notif-queue`, `audit-queue`), the `nica-erp` bus, and rules with the same shape as production.

LocalStack community **does not** support standalone EventBridge Scheduler. The outbox publisher runs as a Python loop locally via `make worker-outbox` (`asyncio.sleep(60)`); the rule's `schedule_expression` is exercised end-to-end when wired to LocalStack if parity with prod is required.

---

## Commands

`make help` lists every available target. Grouped by purpose:

```bash
# Setup (once)
make doctor                              # verify uv, node, pnpm, docker on PATH
make install                             # uv sync + pnpm install
make hooks                               # install pre-commit git hooks
cp .env.local.example .env.local         # secrets at the repo root, loaded by `bootstrap.settings`

# Daily flow
make local-up                            # Postgres + LocalStack + Mailpit
make migrate                             # alembic upgrade head
make api                                 # http://localhost:8000 (Swagger at /docs)
make web                                 # http://localhost:5173
make local-down                          # stop containers (volume persists)

# Migrations
make migrate-down                        # alembic downgrade -1
make makemigration M="add foo table"     # empty revision
make makemigration-auto M="add foo col"  # autogenerate from models

# Quality
make test                                # pytest
make lint                                # ruff + mypy + import-linter + pnpm typecheck + lint
make format                              # ruff format + prettier
```

First time on the web side: `cd apps/web && pnpm gen:api` regenerates the typed OpenAPI client from `/openapi.json`.

> Future-sprint targets (not yet wired): `make seed` (demo data), `make worker-outbox` / `make worker-audit` / `make worker-notif` (Python loops mirroring the prod Lambdas). Sprint 00 doc notes the full list of deferred targets.

---

## Real vs mock by service

| Service | Local |
|---|---|
| PostgreSQL | Real container |
| S3, SQS, EventBridge, SSM Parameter Store | LocalStack |
| EventBridge `Rules` with `schedule_expression` | LocalStack (`events` service); alternative: Python loop |
| Cognito | `IdentityProviderLocal` (LocalStack community does not cover Cognito) |
| SES | Mailpit (SMTP + inspector UI) |
| BCN (FX rate) | Mock with fixed rate `FX_RATE_USD_NIO=36.5` |
| ALB, Fargate, Lambda | Not applicable (uvicorn + processes) |

---

## `IdentityProviderLocal`

Why not Cognito on LocalStack: [ADR-0005](adr/0005-cognito-with-local-idp.md). Table `auth_local_users` — full schema in [06 — Security model §Local adapter](06-security-model.md#local-adapter-identityproviderlocal). `citext` enabled with `CREATE EXTENSION IF NOT EXISTS citext;` in an early Alembic migration (runs in RDS too). JWT HS256 with `LOCAL_JWT_SECRET`, same claim shape as Cognito. Mailpit captures verification and reset codes.

---

## Environment variables

`.env.local` (gitignored; `.env.local.example` is committed):

```ini
APP_ENV=local
DATABASE_URL=postgresql+asyncpg://nica_erp:nica_erp@localhost:5432/nica_erp
# Alembic CLI is sync → psycopg. API runtime is async → asyncpg.
ALEMBIC_DATABASE_URL=postgresql+psycopg://nica_erp:nica_erp@localhost:5432/nica_erp

AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_REGION=us-east-1

S3_FILES_BUCKET=nica-erp-files
EVENTBRIDGE_BUS_NAME=nica-erp
SQS_NOTIF_QUEUE_URL=http://localhost:4566/000000000000/notif-queue
SQS_AUDIT_QUEUE_URL=http://localhost:4566/000000000000/audit-queue

SMTP_HOST=localhost
SMTP_PORT=1025
# The Mailpit sender address is pinned in `EmailSenderSmtp` (`noreply@local.nica-erp.dev`);
# AWS uses `SES_FROM_ADDRESS` instead.

CORS_ALLOWED_ORIGINS=["http://localhost:5173"]

# Identity (local IdP):
LOCAL_JWT_SECRET=...   # openssl rand -hex 32 — required when APP_ENV=local
# Issuer / audience are pinned in the adapter to nica-erp-local-idp / nica-erp-local.

# Cognito (blank locally; populated by `make deploy` for AWS):
COGNITO_USER_POOL_ID=
COGNITO_APP_CLIENT_ID=
COGNITO_USER_POOL_DOMAIN=
COGNITO_REGION=us-east-1
SES_FROM_ADDRESS=

# Added in sprint 06 (FX/taxes):
FX_RATE_USD_NIO=36.5
```

`scripts/gen-local-secrets.sh` generates all local secrets in one shot. `boto3` honors `AWS_ENDPOINT_URL` → the S3/SQS/EventBridge adapters are the same binaries as in prod.

---

## Seed

`scripts/seed-dev.py`: one tenant "Distribuidora Demo S.A." (fictional RUC, fictional DGI authorization, Managua), 2 users (`owner@demo.test`, `staff@demo.test` with `Demo1234!`), 5 products, 3 customers, 1 warehouse with stock, 1 active `NumberSequence` (range 0001-1000), `tax_config` with VAT 15% and IMI 1%.

---

## Tests

Detail in [14 — Testing](14-testing.md). Quick reference:

| Level | How |
|---|---|
| `unit` | `pytest -m unit`. No DB or network; adapters mocked. |
| `integration` | `pytest -m integration` with `testcontainers` (real Postgres). |
| `e2e` | `pytest -m e2e` with `httpx` async against uvicorn + Postgres in container. Critical flows (signup → tenant → invoice → pdf, RLS isolation). |

Workers: unit (handler with mocks) + integration (real handler against LocalStack SQS).

---

## When to touch AWS

Almost never. Justified cases: validate the Cognito adapter once per auth feature; verify SES sandbox verification flow; check WeasyPrint container fonts (local uses system fonts). A `make deploy → test → make destroy` cycle costs ~$5-10.

---

## Gotchas

- LocalStack forgets state on restart. Set `LOCALSTACK_PERSISTENCE=1` if that becomes a problem.
- EventBridge → SQS on LocalStack takes 1-2 s; tests should `asyncio.sleep` or poll with timeout.
- PgBouncer transaction mode: verify `SET LOCAL` still works if introduced.
- `ModuleNotFoundError: bootstrap` / `shared_kernel` → missing `uv sync` (src-layout; imports are flat, no wrapping package).

---

## References
- [ADR-0005](adr/0005-cognito-with-local-idp.md) — Cognito + local IdP rationale
- [06 — Security model](06-security-model.md) — Auth detail
- [11 — Deployment](11-deployment.md) — When you do need to deploy
- [14 — Testing](14-testing.md) — Test strategy
- [16 — Tooling](16-tooling.md) — Linters, formatters, type checks
