# ADR-0018 — Rolling deploys: every sprint closes deployable to AWS

**Status**: Accepted
**Date**: 2026-05-23

## Context
Two problems with concentrating deployment at the end of the MVP: (1) the product has an explicit portfolio component — without a public URL for 8 sprints there is nothing to show; (2) all "this on AWS" debt piles up at the end, and a badly designed port abstraction only surfaces after 8 sprints. The cost philosophy of [ADR-0003](0003-deploy-destroy-per-env.md) (deploy/destroy on demand) makes per-sprint deploy viable.

## Decision
**Rolling deploys starting in sprint 01. Every sprint from 01 onward closes with the capability deployed to AWS.**

Cadence:

- **Sprint 00 — Local foundation.** Monorepo bootstrap, `shared_kernel`, Postgres, Alembic, RLS scaffolding. No AWS (a walking skeleton on AWS without Postgres + Alembic adds nothing).
- **Sprint 01 — First AWS deploy.** Terraform bootstrap (state, ECR) + ephemeral modules (VPC, RDS, ECS, ALB) + persistent (S3 + CloudFront, [ADR-0020](0020-no-custom-domain-mvp.md)). Outcome: `make bootstrap && make deploy` brings up the walking skeleton; `/healthz` and SPA at `https://<dist>.cloudfront.net/`.
- **Sprints 02-08 — Vertical slices.** Each sprint delivers a bounded context with backend + frontend + **Local↔AWS port swap within the sprint** + `make deploy` exercising the slice + `make destroy` at close.
- **Sprint 09 — MVP validation.** Parameterized contract tests (consolidated verification), observability polish, video walkthrough, cost audit. No new features.

**Vertical slice inside the sprint** (not a pipeline between sprints): one person builds the monorepo ([ADR-0009](0009-frontend-stack.md)); a three-feature pipeline adds overhead without benefit. Internal order: backend → OpenAPI → typed client → frontend → `make deploy` → end-to-end verification → `make destroy`.

### Incremental swap, not final swap

| Port | Sprint that introduces it | Local→AWS swap |
|---|---|---|
| `SecretsProvider` (SSM) | 01 — AWS Terraform | `.env.local` ↔ SSM SecureString |
| `IdentityProvider` (Cognito) | 02 — Identity | Real login at sprint close |
| `EmailSender` (SES) | 02 — Identity | Verification email via SES sandbox |
| `FileStorage` (S3 `files`) | 05 — Sales MVP | PDF downloadable from real bucket |
| `FxRateProvider` (BCN) | 06 — Taxes | Scraper Lambda on scheduled rule |
| `EventPublisher` (EventBridge) | 07 — Outbox | Event published to the real bus |

Full port catalog (including `OutboxWriter`, `Clock`, `Cache`) and canonical wiring pattern in [`../sprints/README.md` §Adapters by environment](../sprints/README.md#adapters-by-environment). Sprint 09 runs parameterized contract tests as cross-verification, not as the first validation point.

## Consequences
- (+) Each sprint produces a public, demo-able URL from sprint 01 onward.
- (+) Per-sprint swap, not deferred: a bad abstraction surfaces where it is introduced.
- (+) The operator internalizes `make deploy` / `make destroy` (~8 cycles by sprint 09).
- (+) Preserves the cost philosophy ([ADR-0003](0003-deploy-destroy-per-env.md)): idle ~$0/month ([ADR-0020](0020-no-custom-domain-mvp.md)); session ~$2.70/day. One session × 9 sprints ≈ $25-50 during the MVP.
- (+) No CI/CD required: `make deploy` from the dev machine.
- (-) Sprints 02-08 are wider (they include the swap + deploy/destroy cycle).
- (-) **Sprint 01 concentrates Terraform risk.** Mitigations: bounded scope (empty frontend, Cognito without custom attrs, one placeholder Lambda); post-deploy checklist (terraform exit 0, `/healthz` with `{"db":"ok"}`, ECS RUNNING, SPA 200, logs without tracebacks); 1-day time-box before declaring a blocker; `make destroy` always works even if deploy partially failed ([`../11-deployment.md` §Incidents](../11-deployment.md)).
- (-) Sprint 09 owns consolidated contract tests and the video walkthrough as cross-cutting validation, without the pressure of a first deploy.

## Alternatives
- **Deploy at the end** — rejected: concentrates risk at the close.
- **Continuous CI/CD with an always-on stack** — rejected: violates the cost philosophy ([ADR-0003](0003-deploy-destroy-per-env.md), [ADR-0023](0023-no-ci-cd-mvp.md)).
- **Rolling deploys with local foundation** — chosen.

## Revisit triggers
- Sprint 01 fails the post-deploy checklist twice in a row — re-evaluate scope of the first deploy.
- A vertical slice cannot fit a swap + deploy + destroy inside one sprint repeatedly — re-evaluate cadence.
- The product loses its portfolio requirement (e.g., paying customer arrives early) — different deploy strategy may apply.
