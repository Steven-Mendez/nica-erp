# 08 — API Conventions

Cross-cutting HTTP API contract: errors, pagination, idempotency, versioning, headers. Endpoint catalog lives in **OpenAPI** (`/docs`, `/openapi.json`) — generated from the FastAPI source. The SPA's typed client is regenerated from there on every sprint.

This doc owns the **conventions**. Per-endpoint detail lives in OpenAPI; per-permission detail lives in [06 — Security model](06-security-model.md).

---

## Versioning

`/v1` URL prefix; additive within version; breaking changes ship as `/v2` per [ADR-0027](adr/0027-api-versioning.md). The unversioned root only exposes `/healthz`, `/readyz`, `/docs`, `/openapi.json`.

`Deprecation: true` and `Sunset: <RFC 7231 date>` headers ride on `/v1` responses from the moment `/v2` ships, for a minimum 90-day sunset window.

---

## Auth

`Authorization: Bearer <jwt>` on every request unless explicitly public. Tenant scope is carried in the JWT claim `custom:active_tenant`, **never** in the URL. Detail in [06 — Security model](06-security-model.md).

Public endpoints: `/v1/auth/register`, `/v1/auth/confirm-signup`, `/v1/auth/resend-code`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/password/forgot`, `/v1/auth/password/reset`, `/v1/invitations/{token}/accept`, `/healthz`, `/readyz`.

---

## Headers

| Header | Direction | Meaning |
|---|---|---|
| `Authorization: Bearer <jwt>` | request | Required except on public endpoints |
| `Idempotency-Key: <uuid>` | request | Optional on mutating POST/PATCH (see [Idempotency](#idempotency)) |
| `X-Correlation-ID: <uuid>` | request/response | Tracing; backend generates if absent; flows through outbox |
| `X-Request-ID: <uuid>` | response | Unique per request |
| `Retry-After: <seconds>` | response | Accompanies `429` and `503` |
| `Sunset: <RFC 7231 date>` | response | Set on `/v1` once `/v2` ships |
| `Deprecation: true` | response | Set on `/v1` once `/v2` ships |
| `Content-Type: application/problem+json` | response | All 4xx/5xx |

---

## Pagination

Two contracts, two use cases.

### Cursor pagination (large or growing lists)

Used on: `invoices`, `audit-log`, `inventory/movements`, `kardex`, `outbox`, anywhere row count can exceed thousands.

Request: `?cursor=<opaque>&page_size=50`
Response: `{ items: [...], next_cursor: null | string, has_more: boolean }`

- Default `page_size = 25`, max `100`.
- `next_cursor` is opaque, HMAC-signed (per [ADR-0016](adr/0016-cursor-pagination.md)); clients never construct it.
- No `prev_cursor`, no `total` (computing total is expensive at scale).

### Offset pagination (finite catalogs)

Used on: `products`, `customers`, `suppliers`, `categories`, `units-of-measure`, `number-sequences`.

Request: `?page=1&page_size=25`
Response: `{ items: [...], page, page_size, total, total_pages }`

- Default `page_size = 25`, max `100`.
- Hard cap: `page * page_size <= 1000`. Exceeding returns `400` with `code=pagination.offset-too-deep` — clients should switch to cursor or refine the query.

---

## Filtering and search

- Query parameters with native types (ISO 8601 dates, booleans, numbers).
- Multiple values: `?status=issued&status=paid`.
- Ranges: `?from=<iso>&to=<iso>` (inclusive lower, exclusive upper).
- Text search: `q=<term>` uses `ILIKE '%term%'` in MVP. Future degradation to `pg_trgm` GIN index without contract change.

---

## Idempotency

`Idempotency-Key: <uuid>` is optional on mutating endpoints and **required on operations that are dangerous to retry** (issuing an invoice, applying a payment, reversing a payment). It does **not** apply to `GET`, `DELETE`, or `/v1/auth/*` (which handle their own retries).

TTL: 24 hours. Storage: `idempotency_keys` table, PK `(tenant_id, key, endpoint)`. Housekeeping Lambda prunes expired entries.

### Behavior

| Situation | Response |
|---|---|
| No prior record for `(tenant_id, key, endpoint)` | Execute, persist `(request_hash, response_status, response_body)`, return |
| Prior record, same `request_hash` | Return the cached `response_body` with `Idempotency-Replayed: true` |
| Prior record, different `request_hash` | `409 Conflict`, code `idempotency.key_reused_with_different_payload` |

`request_hash` = SHA-256 of the JSON-normalized body (keys sorted, no whitespace). Headers do not enter the hash.

### Recommended use

| Endpoint class | Idempotency-Key |
|---|---|
| `POST /v1/invoices/{id}/issue` | **Required** — allocates DGI sequence, decrements stock, emits `InvoiceIssued` |
| `POST /v1/invoices/{id}/cancel` | **Required** |
| `POST /v1/credit-notes`, `POST /v1/credit-notes/{id}/issue` | **Required** |
| `POST /v1/debit-notes`, `POST /v1/debit-notes/{id}/issue` | **Required** |
| `POST /v1/customer-payments` | Recommended — prevents double-recorded payments |
| `POST /v1/customer-payments/{id}/apply`, `.../reverse` | **Required** |
| `POST /v1/inventory/adjustments`, `.../transfers` | **Required** |
| `POST /v1/invoices` (create draft) | Recommended — operator double-click |
| `POST /v1/products`, `/customers`, `/suppliers` | Optional |
| `POST /v1/quotations`, `.../convert` | Optional |
| `POST /v1/tenants`, `.../invitations` | Optional |
| `POST /v1/auth/*` | Not applicable |
| `POST /v1/notifications/{id}/read` | Not applicable (idempotent by nature) |

---

## Errors — RFC 7807 Problem Details

All 4xx/5xx responses use `Content-Type: application/problem+json` ([ADR-0015](adr/0015-rfc7807-errors.md)).

```json
{
  "type": "https://<dist-id>.cloudfront.net/api/docs/errors/invoice.cannot_cancel_with_payments",
  "title": "Cannot cancel an invoice with applied payments",
  "status": 409,
  "detail": "The invoice has 2 applied payments that must be reversed first.",
  "instance": "/v1/invoices/01HXYZ.../cancel",
  "trace_id": "01HXYZABCD",
  "code": "invoice.cannot_cancel_with_payments",
  "applied_payments": ["01HXYZ1", "01HXYZ2"]
}
```

| Field | Meaning |
|---|---|
| `type` | Stable URI; documentation page exists at that URL |
| `title` | Stable per code; i18n future |
| `status` | Repeats HTTP status |
| `detail` | Instance-specific message |
| `instance` | URL of the failing request |
| `trace_id` | `correlation_id` for log correlation |
| `code` | Stable, parseable identifier (`<context>.<error>`) |
| Domain extensions | Additional context fields (`applied_payments`, `field_errors`, etc.) |

Validation errors (`422`) include `field_errors: [{ field, code, message }]`.

### Exception → HTTP → code map

| Exception (layer) | HTTP | `code` |
|---|---|---|
| `RequestValidationError` (FastAPI/Pydantic) | 422 | `validation.request_invalid` |
| `DomainError` base | 400 | `<context>.<error>` |
| `NotFoundError` (including RLS-hidden) | 404 | `<resource>.not_found` |
| `ConflictError` (state/aggregate) | 409 | `<context>.<conflict>` |
| `IdempotencyConflictError` | 409 | `idempotency.key_reused_with_different_payload` |
| `AuthenticationError` | 401 | `auth.invalid_credentials` / `auth.token_expired` |
| `ForbiddenError` (missing permission) | 403 | `missing-permission` (extension `missing: [...]`) |
| `TenantScopeError` (forged JWT detected) | 403 | `tenant.not_member` |
| `NumberSequenceExhaustedError` | 409 | `sales.number_sequence_exhausted` |
| `PaginationOffsetTooDeepError` | 400 | `pagination.offset-too-deep` |
| `RateLimitedError` (reserved) | 429 | `rate_limit.exceeded` |
| Unhandled | 500 | `internal.unexpected` |

### Status codes in use

`200`, `201`, `204`, `400` (business rule), `401`, `403`, `404` (also RLS-hidden), `409` (state / idempotency), `422` (request validation), `429` (rate limit, reserved), `500`.

**400 vs 422**: validation of request shape → 422; business rule violation → 400. Distinction enforced at the application layer.

---

## Soft delete

`DELETE` on catalog resources (`products`, `customers`, `suppliers`, `warehouses`, `categories`) sets `active=false`, `deactivated_at=now()`. Lists exclude inactive by default; `?active=true|false|any` overrides. `GET /{id}` returns 200 with `"active": false` (preserves historical references).

Fiscal documents (`invoices`, `payments`, `credit_notes`, `debit_notes`, `audit_log_entries`) **do not accept DELETE** per [ADR-0014](adr/0014-soft-delete.md). Cancel or compensate (credit/debit note).

---

## Rate limiting

`429 + Retry-After` is reserved in the contract. MVP does not enforce (stack idle most of the time, known tenants). Future enforcement at CloudFront/ALB level. Plan in [10 — Infrastructure](10-infrastructure.md).

---

## Health

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | `{ status, version, git_sha, db, alembic_revision }` — public |
| `GET /readyz` | Deployment gate; checks DB connection, SSM accessibility — public |

---

## Endpoint catalog

Not in this document. The authoritative catalog is OpenAPI:

- **Local dev**: `http://localhost:8000/docs`
- **Deployed**: `https://<dist-id>.cloudfront.net/api/docs`
- **Machine-readable**: `/openapi.json`
- **TypeScript client**: regenerated from OpenAPI on every sprint via `pnpm gen:api` (see [09 — Frontend](09-frontend.md))

Per-endpoint permission requirements are documented in the OpenAPI operation's `description` field and enforced by the FastAPI `require(...)` dependency ([06 — Security model](06-security-model.md)).

---

## References
- [ADR-0015](adr/0015-rfc7807-errors.md) — Problem Details
- [ADR-0016](adr/0016-cursor-pagination.md) — Pagination
- [ADR-0027](adr/0027-api-versioning.md) — Versioning policy
- [06 — Security model](06-security-model.md) — Auth, RBAC, permission matrix
- [07 — Events and outbox](07-events-and-outbox.md) — How async APIs publish events
- [09 — Frontend](09-frontend.md) — OpenAPI client generation
