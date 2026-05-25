# ADR-0027 — API versioning

**Status**: Accepted
**Date**: 2026-05-23

## Context
The HTTP API is consumed by the SPA from day one ([ADR-0009](0009-frontend-stack.md)) and by future third parties (mobile, integrations) post-MVP. Without an explicit versioning policy, every change risks breaking unknown consumers, and there is no shared expectation of what counts as breaking. [ADR-0012](0012-event-versioning.md) covers integration events; this ADR covers the synchronous HTTP API.

## Decision
**URL-prefixed major versions (`/v1`, `/v2`); additive changes within a version; breaking changes get a new prefix with a documented sunset.**

### Versioning rules
- The current version is `/v1`. All endpoints live under it. The unversioned root (`/`) only exposes `/healthz`, `/docs`, and `/openapi.json`.
- **Additive changes are not breaking**: adding a field to a response, adding an optional request field with a server-side default, adding a new endpoint, adding a new enum value to an open enum.
- **Breaking changes require `/v2`**: removing a field, renaming a field, changing a field's type or nullability, tightening validation, removing an endpoint, changing an enum from open to closed, changing default behavior, changing pagination contract ([ADR-0016](0016-cursor-pagination.md)) shape.
- **`/v1` and `/v2` run side by side** for at least one full release cycle (initially: 90 days minimum) and serve from the same backend with branch-based handlers in `infrastructure/http/v1/` and `infrastructure/http/v2/`.
- **Sunset signaling** uses the standard `Sunset` HTTP header (`Sunset: Sat, 31 Dec 2026 23:59:59 GMT`) on every `/v1` response once `/v2` ships. `Deprecation: true` is set the same way.
- **Within a version, OpenAPI is the contract.** The generated TypeScript client ([ADR-0009](0009-frontend-stack.md)) is the proof that the SPA tracks the contract. Drift between OpenAPI and implementation is a CI fail.

### Out of scope for `/v1`
- Header-based versioning (`Accept: application/vnd.pyme-erp.v2+json`). Rejected for being invisible in URLs/logs/CDN paths.
- Quarterly auto-bumps. Versions only exist when forced by a breaking change.
- Per-endpoint versioning. Rejected for combinatorial growth.

## Consequences
- (+) Single, visible source of truth for what version a client is on (the URL).
- (+) CDN/CloudFront cache keys naturally segment by version.
- (+) Sunset header gives third parties a programmatic migration signal.
- (+) Aligns with [ADR-0012](0012-event-versioning.md)'s "versions only on breaking changes" rule.
- (−) Two handler trees in `infrastructure/http/` during a sunset window. Duplication is intentional — sharing application layer use cases keeps it shallow.
- (−) Sunset enforcement is operator discipline, not automated. Mitigated by alarm: log a metric when `/v1` is hit after the sunset date.
- (−) Pre-MVP, only the SPA consumes the API, so `/v1` is mostly internal. Versioning ceremony seems heavy — accepted as a one-time setup cost.

## Alternatives
- **Header-based version negotiation** — rejected: invisible in logs and CDN cache keys, harder to debug.
- **No versioning until first breaking change** — rejected: the breaking change becomes a panic if it happens before policy is set.
- **Date-based versions (`/2026-05-23/...`)** — rejected: Stripe-style policy is overkill for the scale and adds cognitive overhead.
- **Per-resource versioning** — rejected: combinatorial growth, no benefit at MVP scale.

## Revisit triggers
- First third-party integration consumes the API — confirm 90-day sunset is enough; lengthen if needed.
- First breaking change actually happens — exercise the `/v2` path end-to-end and refine the playbook.
- More than two concurrent versions in flight — re-evaluate handler-tree duplication strategy.
- A client cannot upgrade in the sunset window — escalation path defined in [`../13-operations.md`](../13-operations.md).
