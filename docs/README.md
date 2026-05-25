# docs/

Product, architecture, operations, and reference for **nica-erp**.

**Suggested reading order**: [01](01-overview.md) → [02](02-architecture.md) → [03](03-bounded-contexts.md) → [05](05-multi-tenancy.md) → [06](06-security-model.md) → [11](11-deployment.md) → [15](15-local-development.md). Then [`adr/`](adr/README.md) for the *why* and [`sprints/`](sprints/README.md) for the build sequence.

## Index

### Foundation
| # | Doc | Scope |
|---|---|---|
| [01](01-overview.md) | Overview | Product, audience, non-goals |
| [02](02-architecture.md) | Architecture | Hexagonal + DDD, layering, dependency rules |
| [03](03-bounded-contexts.md) | Bounded contexts | Context map, integration patterns |
| [04](04-domain-model.md) | Domain model | ER overview, aggregates, invariants |
| [05](05-multi-tenancy.md) | Multi-tenancy | Tenant model, RLS, lifecycle |
| [06](06-security-model.md) | Security model | Auth, RBAC, tokens, secrets, threat surface |
| [07](07-events-and-outbox.md) | Events & outbox | Domain/integration events, dispatch, versioning |

### Interfaces
| # | Doc | Scope |
|---|---|---|
| [08](08-api-conventions.md) | API conventions | Errors, pagination, idempotency, versioning |
| [09](09-frontend.md) | Frontend | SPA stack, routing, state |

### Operations
| # | Doc | Scope |
|---|---|---|
| [10](10-infrastructure.md) | Infrastructure | AWS topology, capacity, networking |
| [11](11-deployment.md) | Deployment | Terraform, deploy/destroy, rolling deploys |
| [12](12-observability.md) | Observability | Logs, metrics, dashboards, debug runbook |
| [13](13-operations.md) | Operations | Runbooks: restore, incident, tenant lifecycle ops |
| [14](14-testing.md) | Testing | Test pyramid, RLS pattern, N+1 gate |
| [15](15-local-development.md) | Local development | Docker Compose, local IdP, seeds |
| [16](16-tooling.md) | Tooling | Linters, type checkers, pre-commit |

### Reference
| # | Doc | Scope |
|---|---|---|
| [17](17-compliance-nicaragua.md) | Compliance — Nicaragua | DGI: IR, IVA, IMI, fiscal calendar |
| [18](18-roadmap.md) | Roadmap | Sprint philosophy + MVP scope |
| [19](19-glossary.md) | Glossary | Domain + tech terms (Spanish ↔ English) |

### Subdirectories
- [`adr/`](adr/README.md) — 29 Architecture Decision Records.
- [`sprints/`](sprints/README.md) — 10 build sprints, rolling deploys per [ADR-0018](adr/0018-rolling-deploys.md).

## Conventions
- English only; Spanish terms in [`19-glossary.md`](19-glossary.md).
- Every architectural choice cites an ADR; every runbook lives in [`13-operations.md`](13-operations.md).
- Diagrams in Mermaid.
- Single source of truth — RBAC matrix in [`06`](06-security-model.md); deploy mechanics in [`11`](11-deployment.md); outbox dispatch in [`07`](07-events-and-outbox.md). Cross-reference, don't duplicate.
