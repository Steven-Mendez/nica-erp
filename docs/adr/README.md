# Architecture Decision Records

One ADR per decision: context, decision, consequences, alternatives, revisit triggers. Pre-implementation: when a decision changes, replace it in place — no history kept.

Template: [`template.md`](template.md).

## Index by theme

### Foundation
| # | Title | Summary |
|---|---|---|
| [ADR-0001](0001-hexagonal-architecture.md) | Hexagonal + DDD | Modular monolith, ports & adapters, bounded contexts |
| [ADR-0002](0002-postgres-rls.md) | Multi-tenancy: pool + RLS | One DB, `tenant_id`, RLS as defense-in-depth |
| [ADR-0010](0010-python-fastapi.md) | Backend stack | Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic |
| [ADR-0011](0011-uuidv7-identifiers.md) | UUIDv7 primary keys | Temporally ordered identifiers, B-tree friendly |

### Auth & security
| # | Title | Summary |
|---|---|---|
| [ADR-0005](0005-cognito-with-local-idp.md) | Cognito Lite + local IdP | Same port, two adapters; offline dev |
| [ADR-0021](0021-ssm-parameter-store.md) | Secrets in SSM Parameter Store | SecureString for persistent secrets; absorbs old secrets ADR |
| [ADR-0022](0022-rbac-model.md) | RBAC: 5 roles + granular permissions | Granular, ownership-hybrid; FastAPI dependency enforces |
| [ADR-0035](0035-onboarding-endpoints-return-session.md) | Onboarding endpoints leave caller session-ready | `confirm-signup` may return tokens; `accept-invitation` may set `active_tenant` on first membership |

### Infrastructure & deploy
| # | Title | Summary |
|---|---|---|
| [ADR-0003](0003-deploy-destroy-per-env.md) | AWS deploy/destroy on demand | Economic tier; stack up only when valuable |
| [ADR-0004](0004-ecs-not-lambda.md) | ECS Fargate for the API | Hot uvicorn process; no cold starts |
| [ADR-0017](0017-backups-pitr.md) | RDS backups by phase + Glacier | Retention scales; final snapshot; DGI 5-year compliance — **Provisional** (pre-launch: `backup_retention=0`) |
| [ADR-0018](0018-rolling-deploys.md) | Rolling deploys per sprint | First deploy sprint 01; each slice swaps a port to its AWS adapter |
| [ADR-0020](0020-no-custom-domain-mvp.md) | No custom domain | CloudFront default + SES sandbox; idle ~$0 |
| [ADR-0023](0023-no-ci-cd-mvp.md) | No auto CI/CD for MVP | GitHub Actions for checks only; manual deploy |
| [ADR-0029](0029-disaster-recovery-posture.md) | Disaster recovery posture | Phase-scoped RTO/RPO; runbook ownership |

### Events & data
| # | Title | Summary |
|---|---|---|
| [ADR-0006](0006-transactional-outbox.md) | Transactional outbox | At-least-once integration events without dual-write |
| [ADR-0007](0007-outbox-dispatch-polling.md) | Outbox dispatch: 60s Lambda polling | MVP polling; explicit upgrade triggers to LISTEN/NOTIFY |
| [ADR-0012](0012-event-versioning.md) | Event versioning | `event_type` stable + `event_version` int; dual-publish on breaking |
| [ADR-0024](0024-observability-baseline.md) | Observability baseline | CloudWatch Logs JSON + EMF + correlation_id; no distributed tracing |
| [ADR-0028](0028-data-migration-strategy.md) | Data migration strategy | Alembic, expand/contract, zero-downtime patterns — **Provisional** (no sprint applies it yet) |

### Domain & UX
| # | Title | Summary |
|---|---|---|
| [ADR-0008](0008-for-update-sequence-allocation.md) | `FOR UPDATE` number sequence | DGI-compliant fiscal numbering, no gaps or duplicates |
| [ADR-0009](0009-frontend-stack.md) | Frontend stack | React + TanStack + Vite + shadcn/ui (single ADR) |
| [ADR-0013](0013-utc-everywhere.md) | UTC at rest; tenant tz at display | `timestamptz` always; cutoffs per tenant tz |
| [ADR-0014](0014-soft-delete.md) | Fiscal append-only; catalogs soft delete | No `DELETE` on fiscals; `active` flag on catalogs |
| [ADR-0015](0015-rfc7807-errors.md) | RFC 7807 Problem Details | `application/problem+json`; domain extensions |
| [ADR-0016](0016-cursor-pagination.md) | Cursor for large lists; offset for catalogs | HMAC-signed cursor; offset ≤ 1000 |
| [ADR-0019](0019-kardex-inventory.md) | Kardex weighted average | Single `(qty, unit_cost)` per SKU |
| [ADR-0026](0026-tenant-lifecycle.md) | Tenant lifecycle | Signup → active → suspended → purged — **Provisional** (states defined; transitions post-MVP) |
| [ADR-0027](0027-api-versioning.md) | API versioning | `/v1` URL prefix; breaking changes get `/v2` |

### Process
| # | Title | Summary |
|---|---|---|
| [ADR-0025](0025-testing-strategy.md) | Testing strategy | Pyramid, contract tests across local/AWS ports |

## Adding an ADR

1. Copy [`template.md`](template.md) → `NNNN-slug-kebab-case.md` with the next sequential number.
2. Fill in all sections. Be explicit about revisit triggers; vague "in the future" doesn't count.
3. Add a row to the appropriate theme above.
4. If replacing an existing decision (pre-implementation): edit the existing ADR in place; do not keep a history copy.
