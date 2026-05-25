# nica-erp

Multi-tenant ERP SaaS for Nicaraguan SMBs. FastAPI + React + AWS, monorepo, one command up / one command down.

> **Status**: sprint 00 — walking skeleton. Only local dev works today; AWS deploy lands in [sprint 01](docs/sprints/01-aws-wiring-rolling-deploys.md).

---

## Quick start

```bash
make doctor                               # verify uv, node, pnpm, docker
make install                              # uv sync + pnpm install
cp .env.local.example apps/api/.env.local
make local-up                             # Postgres + LocalStack + Mailpit
make migrate                              # alembic upgrade head
make api                                  # terminal 1 — :8000 (Swagger /docs)
make web                                  # terminal 2 — :5173
```

First time on the web side: `cd apps/web && pnpm gen:api` to generate the typed OpenAPI client.

Verify: `curl localhost:8000/healthz` → `{"status":"ok","db":"ok","alembic_revision":"0001_..."}`.

Stop everything: `make local-down` (data persists in the `pg_data` volume).

All Make targets: `make help`. Detail in [`docs/15-local-development.md`](docs/15-local-development.md).

---

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic. Hexagonal + DDD. Postgres RLS for multi-tenancy, outbox for at-least-once events.
- **Frontend**: React 18, TS strict, Vite, TanStack (Router/Query/Form), Tailwind + shadcn/ui, Zod, typed OpenAPI client.
- **Infrastructure** (from sprint 01): ECS Fargate, RDS `db.t4g.micro`, Cognito, SES, EventBridge + SQS, CloudFront as the only front door. Ephemeral by default — idle ~$0/mo, session ~$2.70/day.

CI runs static checks only; deploy is manual.

---

## Documentation

See [`docs/`](docs/README.md) for architecture, ADRs, sprint plans, and reference material.
