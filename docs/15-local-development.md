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

`docker/docker-compose.yml`: Postgres 16, LocalStack community (`S3,SQS,events,ssm`), Mailpit. `localstack-init.sh` creates the `pyme-erp-files` bucket, queues + DLQs (`notif-queue`, `audit-queue`), the `pyme-erp` bus, and rules with the same shape as production.

LocalStack community **does not** support standalone EventBridge Scheduler. The outbox publisher runs as a Python loop locally via `make worker-outbox` (`asyncio.sleep(60)`); the rule's `schedule_expression` is exercised end-to-end when wired to LocalStack if parity with prod is required.

---

## Commands

```bash
make local-up               # Postgres + LocalStack + Mailpit
make migrate && make seed   # alembic + demo data
make api                    # http://localhost:8000 (Swagger at /docs)
make web                    # http://localhost:5173

# Workers (separate terminals)
make worker-outbox
make worker-audit
make worker-notif
```

Local workers = Python processes running the same handler as the Lambda; only the harness (loop) and the wiring (LocalStack) differ.

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
DATABASE_URL=postgresql+asyncpg://pyme_erp:pyme_erp@localhost:5432/pyme_erp
# Alembic CLI is sync → psycopg. API runtime is async → asyncpg.
ALEMBIC_DATABASE_URL=postgresql+psycopg://pyme_erp:pyme_erp@localhost:5432/pyme_erp

AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_REGION=us-east-1

S3_FILES_BUCKET=pyme-erp-files
EVENTBRIDGE_BUS_NAME=pyme-erp
SQS_NOTIF_QUEUE_URL=http://localhost:4566/000000000000/notif-queue
SQS_AUDIT_QUEUE_URL=http://localhost:4566/000000000000/audit-queue

SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=noreply@local.pyme-erp.dev

LOCAL_JWT_SECRET=...   # openssl rand -hex 32
LOCAL_JWT_ISSUER=pyme-erp-local
LOCAL_JWT_AUDIENCE=pyme-erp-app

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
- `ModuleNotFoundError: pyme_erp` → missing `uv sync` (src-layout).

---

## References
- [ADR-0005](adr/0005-cognito-with-local-idp.md) — Cognito + local IdP rationale
- [06 — Security model](06-security-model.md) — Auth detail
- [11 — Deployment](11-deployment.md) — When you do need to deploy
- [14 — Testing](14-testing.md) — Test strategy
- [16 — Tooling](16-tooling.md) — Linters, formatters, type checks
