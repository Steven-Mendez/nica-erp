# nica-erp

Multi-tenant ERP SaaS for Nicaraguan SMBs. FastAPI + React + AWS, monorepo, one command up / one command down.

> **Status**: identity context (signup → confirm → login → `/me`) works locally against `IdentityProviderLocal` + Mailpit and on AWS against Cognito + SES. RBAC, tenants, and Postgres RLS are not yet implemented.

---

## Quick start

```bash
make doctor                               # verify uv, node, pnpm, docker
make install                              # uv sync + pnpm install
cp .env.local.example .env.local          # secrets stay at the repo root
make local-up                             # Postgres + LocalStack + Mailpit
APP_ENV=local make migrate                # alembic upgrade head (creates auth_local_users)
make api                                  # terminal 1 — :8000 (Swagger /docs)
make web                                  # terminal 2 — :5173
```

Local URLs:

| Service | URL |
|---|---|
| API (Swagger) | http://localhost:8000/docs |
| SPA | http://localhost:5173 |
| Mailpit (inbox) | http://localhost:8025 |
| Postgres | `postgresql://nica_erp:nica_erp@localhost:5432/nica_erp` |
| LocalStack | http://localhost:4566 |

First time on the web side: `cd apps/web && pnpm gen:api` to generate the typed OpenAPI client.

Verify: `curl localhost:8000/healthz` → `{"status":"ok","db":"ok","alembic_revision":"0002_identity"}`.

Stop everything: `make local-down` (data persists in the `pg_data` volume).

All Make targets: `make help`. Detail in [`docs/15-local-development.md`](docs/15-local-development.md).

### Local auth flow

The signup / login loop runs against `IdentityProviderLocal` (HS256 JWT) and Mailpit (`http://localhost:8025`). End-to-end via cURL:

```bash
# 1. Signup — generic 201, no email-enumeration leak.
curl -s -X POST localhost:8000/v1/auth/register \
  -H 'content-type: application/json' \
  -d '{"email":"yo@test.dev","password":"Demo1234!@xy"}'

# 2. Read the 6-digit code from http://localhost:8025 (Mailpit), then confirm:
curl -s -X POST localhost:8000/v1/auth/confirm-signup \
  -H 'content-type: application/json' \
  -d '{"email":"yo@test.dev","code":"123456"}'

# 3. Login and grab the access token.
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"yo@test.dev","password":"Demo1234!@xy"}' | jq -r .access_token)

# 4. Fetch the authenticated profile.
curl -s localhost:8000/v1/me -H "Authorization: Bearer $TOKEN" | jq
```

SPA equivalent: open `http://localhost:5173/signup`, follow the code from Mailpit, land on `/me`. Tokens live in JS memory only — reload loses the session and routes back to `/login` (full posture in [`docs/06-security-model.md`](docs/06-security-model.md)).

---

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic. Hexagonal + DDD. Postgres RLS for multi-tenancy, outbox for at-least-once events.
- **Frontend**: React 18, TS strict, Vite, TanStack (Router/Query/Form), Tailwind + shadcn/ui, Zod, typed OpenAPI client.
- **Infrastructure** (from sprint 01): ECS Fargate, RDS `db.t4g.micro`, Cognito, SES, EventBridge + SQS, CloudFront as the only front door. Ephemeral by default — idle ~$0/mo, session ~$2.70/day.

CI runs static checks only; deploy is manual.

---

## Documentation

See [`docs/`](docs/README.md) for architecture, ADRs, sprint plans, and reference material.
