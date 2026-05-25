# ADR-0001 — Hexagonal + DDD

**Status**: Accepted
**Date**: 2026-05-23

## Context
ERP with multiple bounded contexts, fiscal compliance, and strict multi-tenancy. The domain must be testable without AWS or a database; modules must be addable without rewrites; adapters (Cognito ↔ local IdP, SES ↔ Mailpit) must be swappable without touching business code.

## Decision
Modular Python monolith (`pyme_erp`) with ports & adapters and tactical DDD. Each bounded context lives under `contexts/<name>/{domain,application,adapters}`. The dependency rule — `domain ← application ← adapters` — is enforced by `import-linter`.

## Consequences
- (+) Domain testable without infra; unit tests in milliseconds.
- (+) Adapter swap proven by construction — see [ADR-0005](0005-cognito-with-local-idp.md).
- (+) Clear boundaries: adding a module or migrating to microservices later does not force a rewrite.
- (−) Boilerplate (ports, DTOs, mappers).
- (−) Risk of speculative ports with no real consumer — keep ports earned by a second adapter, not anticipated.

## Alternatives
- **N-layer clean architecture** — rejected: rigid; degenerates into anemic service classes.
- **Flat MVC** — rejected: mixes business with HTTP/DB.
- **Microservices from day one** — rejected: operational overhead infeasible for a single dev.
- **Modular monolith with hexagonal + tactical DDD + in-process bounded contexts** — chosen.

## Revisit triggers
- A bounded context outgrows the monolith's deploy unit (e.g., independent scaling required).
- A team boundary appears and contexts need separate ownership.
- `import-linter` violations become routine rather than rare — signal that the abstraction is fighting reality.

Detail in [`../02-architecture.md`](../02-architecture.md).
