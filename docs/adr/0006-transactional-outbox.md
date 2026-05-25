# ADR-0006 — Outbox pattern + at-least-once idempotency

**Status**: Accepted
**Date**: 2026-05-23

## Context
Publish events (`InvoiceIssued`, `PaymentReceived`, etc.) to EventBridge without losing any if the network fails between the DB commit and `PutEvents`.

## Decision
Table `outbox(event_id PK UUIDv7, tenant_id, event_type, event_version, aggregate_type, aggregate_id, payload JSONB, occurred_at, correlation_id, published_at NULL, publish_attempts)` written in the same transaction as the command. `outbox_publisher` (MVP: Lambda + EventBridge Scheduler every 60 s, see [ADR-0007](0007-outbox-dispatch-polling.md)) drains in batches (100/iteration, publishes in batches of 10 — `PutEvents` limit), marks `published_at`. Idempotent consumers via `processed_events(consumer, event_id) PRIMARY KEY (consumer, event_id)`; incoming commands via `idempotency_keys`.

## Consequences
- (+) No lost events; a downed bus accumulates and drains on return.
- (+) Events audited with full payload in DB (debugging, recovery).
- (+) `event_version` allows incompatible evolution.
- (−) Latency: the event reaches the bus seconds after commit.
- (−) Consumers must be idempotent.
- (−) `outbox`, `processed_events`, and `idempotency_keys` need housekeeping (daily Lambda at 03:00 `America/Managua`, retentions configurable via SSM). Default retentions: `outbox` 30 d, `processed_events` 7 d, `idempotency_keys` 24 h. Semantics `created_at + retention` (single source = SSM default, no per-row `expires_at` column). Policy and ops in [`../07-events-and-outbox.md §Housekeeping`](../07-events-and-outbox.md#housekeeping); `audit_log_entries` is excluded (append-only per [ADR-0014](0014-soft-delete.md)).

## Alternatives
- **Direct dual write to EventBridge** — rejected: loss under partial failure.
- **CDC (Debezium)** — rejected: more infra (Kafka Connect / DMS), marginal benefit.
- **2PC across DB and bus** — rejected: slow, complex, EventBridge does not support it.
- **Outbox at-least-once + idempotent consumers** — chosen.

## Revisit triggers
- Per-commit latency to the bus becomes a product requirement (e.g., a synchronous downstream needs sub-second propagation).
- Event volume exceeds what a 60 s polling Lambda can drain — switch trigger (see [ADR-0007](0007-outbox-dispatch-polling.md)) or move to CDC.
- A second event sink is added and the at-least-once contract proves too expensive to honor everywhere.

Detail in [`../07-events-and-outbox.md`](../07-events-and-outbox.md).
