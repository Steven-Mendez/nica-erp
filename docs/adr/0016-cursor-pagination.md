# ADR-0016 — Cursor pagination for large lists; offset for small catalogs

**Status**: Accepted
**Date**: 2026-05-23

## Context
Lists without a natural ceiling (`invoices` and derivatives, `audit_log_entries`, `kardex_movements`, `outbox`) coexist with bounded catalogs (`products`, `customers`, `suppliers`, `tenants`, `users`, `number_sequences`). `LIMIT N OFFSET M` degrades with large tables; cursor (keyset) keeps constant time but loses "jump to page 17", useful in small catalogs.

## Decision
**Cursor on high-volume lists; offset on bounded catalogs; both in OpenAPI under `components/parameters/` and `components/schemas/`.**

### Cursor endpoints
`GET /v1/invoices`, `credit-notes`, `debit-notes`, `customer-payments`, `audit-log`, `kardex`, `outbox`.

- Query: `?cursor=<opaque>&page_size=<int>`. Default 25, max 100.
- Stable order `(timestamp_col DESC, id DESC)` with UUIDv7 tiebreaker ([ADR-0011](0011-uuidv7-identifiers.md)).
- **Cursor**: url-safe base64 of `{"k", "v", "i"}` **signed with HMAC** (key in SSM Parameter Store SecureString — [ADR-0021](0021-ssm-parameter-store.md)) to prevent cross-tenant manipulation.
- Response: `{ items, next_cursor, has_more }`. No `prev_cursor` nor `total`.

### Offset endpoints
`GET /v1/products`, `customers`, `suppliers`, `tenants`, `users`, `number-sequences`.

- Query: `?page=<int>&page_size=<int>`. Default `page=1&page_size=25`, max 100.
- Absolute cap: `page * page_size <= 1000`. Overflow → 400 `code=pagination.offset-too-deep` ([ADR-0015](0015-rfc7807-errors.md), mapping in [`../08-api-conventions.md`](../08-api-conventions.md)) suggesting `?q=`.
- Response: `{ items, page, page_size, total, total_pages }`. `total` via `COUNT(*)` acceptable on bounded tables.

### OpenAPI
- `components/parameters/`: `CursorParam`, `PageSizeParam`, `PageParam`.
- `components/schemas/`: `CursorPage<T>`, `OffsetPage<T>`. The generated client types the response ([ADR-0009](0009-frontend-stack.md)).

## Consequences
- (+) High volume: constant time per page, independent of table size.
- (+) Catalogs: classic numbered-page UX.
- (+) Opaque signed cursor allows changing internal ordering without breaking clients.
- (+) The 1000 cap on offset prevents queries that would saturate the DB.
- (+) Uniform OpenAPI: two typed shapes.
- (−) Two contracts in the frontend. Mitigated with `useCursorList()` / `useOffsetList()` hooks ([09 — Frontend](../09-frontend.md)).
- (−) **Rotating the HMAC key invalidates in-flight cursors.** Policy: same "deliberate manual rotation" rule as the JWT key ([ADR-0021](0021-ssm-parameter-store.md)). If at some point rotation without downtime is required, add a `kid` field to the cursor and accept the two most recent keys.
- (−) No `total` nor `prev_cursor` in cursor: no "page 3 of 187". Acceptable on lists of millions.
- (−) UUIDv7 gives approximate monotonic tiebreaker, not strict between nodes. Sufficient with a single ECS writer; verify with horizontal write-scaling.

## Alternatives
- **Universal offset** — rejected: degrades on large tables.
- **Universal cursor** — rejected: over-design for lists < 1000.
- **Keyset with exposed tiebreaker** — rejected: opaque cursor allows changing internal order without breaking clients.
- **Hybrid by table type** — chosen.

## Revisit triggers
- Horizontal write-scaling (more than one ECS writer) — the monotonic UUIDv7 tiebreaker may no longer hold across nodes.
- A catalog table grows past the 1000-row offset cap regularly — promote to cursor.
