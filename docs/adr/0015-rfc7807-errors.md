# ADR-0015 — HTTP errors in RFC 7807 Problem Details JSON format

**Status**: Accepted
**Date**: 2026-05-23

## Context
Clients (the in-house frontend [ADR-0009](0009-frontend-stack.md), curl/Postman, future third parties) need to programmatically distinguish validation vs conflict vs not-found vs auth vs transient. FastAPI's default (`{"detail": "..."}`) is not standard, not typed, and does not correlate with logs.

## Decision
**Every error response uses `Content-Type: application/problem+json` following RFC 7807, with domain extensions (`trace_id`, `tenant_id`, `field_errors`, `retry_after`).**

Canonical shape and full examples: [08 — API conventions](../08-api-conventions.md).

- `type`: stable URI to `/docs/errors/<slug>`. Each type has an entry in the doc.
- `instance`: endpoint path, without query string or sensitive IDs.
- `trace_id`: request `correlation_id` ([ADR-0024](0024-observability-baseline.md)).
- Uncontrolled exceptions return 500 with a generic `detail` (no stack or SQL).

### Main mapping (middleware `bootstrap/error_handlers.py`)

| Domain exception | HTTP | `type` slug |
|---|---|---|
| `ValidationError` (Pydantic body) | 400 | `invalid-request-body` |
| `ConflictError` / `IdempotencyConflictError` | 409 | `state-conflict` / `idempotency-key-conflict` |
| `NotFoundError` | 404 | `resource-not-found` |

Full table (Auth, Tenant, RateLimit, NumberSequence, etc.) in [`../08-api-conventions.md`](../08-api-conventions.md).

## Consequences
- (+) Standard format; third parties do not require proprietary documentation.
- (+) `trace_id` correlates errors with CloudWatch Insights — diagnosis in 30 s.
- (+) Extensions enrich without breaking the canonical shape.
- (+) Centralized mapping: use cases raise exceptions, do not return HTTP codes.
- (−) Migrating from the default requires disabling built-in exception handlers. One-time work.
- (−) Sync between `/docs/errors/<slug>` and the middleware table is manual. Mitigable with a pending test.
- (−) `detail` must not reveal sensitive info — discipline on every `raise`.
- (−) Some middleboxes change `Content-Type` to `application/json`. Clients inspect `type`.

## Alternatives
- **FastAPI default** — rejected: no stable type, no `trace_id`.
- **JSON:API errors** — rejected: over-designed.
- **GraphQL-style errors** — rejected: API is REST.
- **RFC 7807 Problem Details** — chosen (IETF standard; RFC 9457 updates it).

## Revisit triggers
- Adoption of RFC 9457 (obsoletes 7807) brings a feature we need.
- A real client (e.g., third-party integrator) reports the `application/problem+json` content-type as a blocker — consider negotiated fallback.
