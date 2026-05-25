# nica-erp

Multi-tenant ERP SaaS for Nicaraguan SMBs. Python backend (FastAPI, hexagonal + DDD), React frontend (TanStack + Vite + shadcn/ui), AWS infrastructure via Terraform. One command brings the stack up, another tears it down.

> **Status**: pre-implementation. Build starts with [sprint 00](docs/sprints/00-walking-skeleton.md). Roadmap in [`docs/18-roadmap.md`](docs/18-roadmap.md).

---

## Stack and operation

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic. Multi-tenancy via Postgres RLS. At-least-once outbox.
- **Frontend**: React 18 + TS strict, Vite, TanStack (Router/Query/Table/Form), Tailwind, shadcn/ui, Zod. Typed OpenAPI client.
- **Infrastructure**: ECS Fargate `0.25/0.5`, RDS `db.t4g.micro` single-AZ, Cognito Lite, SES sandbox, EventBridge + SQS. **CloudFront default `*.cloudfront.net` as the only front-door** ([ADR-0020](docs/adr/0020-no-custom-domain-mvp.md)): SPA at `/*`, API at `/api/*`. Secrets in SSM Parameter Store ([ADR-0021](docs/adr/0021-ssm-parameter-store.md)).
- **Operation**: `make local-up` for dev; `make deploy` / `make destroy` for ephemeral AWS; `make deploy-web` for the persistent frontend; `make wipe` for full teardown.
- **Rolling deploys** ([ADR-0018](docs/adr/0018-rolling-deploys.md)): from [sprint 01](docs/sprints/01-aws-wiring-rolling-deploys.md) every slice is verified against `https://<dist-id>.cloudfront.net/` and torn down at close.
- **Cost**: idle ~$0/month. Session ~$2.70/day. Breakdown in [`docs/10-infrastructure.md`](docs/10-infrastructure.md).
- **CI**: static verification only in GitHub Actions; deploy is manual ([ADR-0023](docs/adr/0023-no-ci-cd-mvp.md)).

---

## Quick start — local

Requires `uv`, `pnpm`, Docker.

```bash
make install        # uv sync + pnpm install
make local-up       # Postgres + LocalStack + Mailpit
make migrate && make seed
make api            # http://localhost:8000 (Swagger at /docs)
make web            # http://localhost:5173
```

Adapter swap (`IdentityProviderLocal`, Mailpit, LocalStack) ↔ AWS equivalents happens in `bootstrap/container.py` based on `APP_ENV`. Detail in [`docs/15-local-development.md`](docs/15-local-development.md).

## Quick start — AWS

Requires AWS credentials, Terraform 1.7+, Docker.

```bash
make bootstrap      # one-time: S3 state, DynamoDB lock, ECR, S3 web + CloudFront
make deploy         # build + push + apply + migrate (~12 min). Prints URL.
make destroy        # tear down the ephemeral stack. RDS lost pre-launch (ADR-0017).
make wipe           # full irreversible teardown.
```

Detail in [`docs/11-deployment.md`](docs/11-deployment.md). Deploy/destroy policy in [ADR-0003](docs/adr/0003-deploy-destroy-per-env.md).

---

## Documentation

Everything in [`docs/`](docs/README.md). Start with [`01-overview.md`](docs/01-overview.md) → [`02-architecture.md`](docs/02-architecture.md) → [`15-local-development.md`](docs/15-local-development.md) → [`18-roadmap.md`](docs/18-roadmap.md).

- 19 numbered docs (foundation, interfaces, operations, reference)
- 29 ADRs in [`docs/adr/`](docs/adr/README.md)
- 10 sprints in [`docs/sprints/`](docs/sprints/README.md)
