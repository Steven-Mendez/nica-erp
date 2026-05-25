# 07 — Events and Outbox

## Two types of events

| Type | Lives in | Emitted by | Consumed by | Transaction |
|---|---|---|---|---|
| **Domain event** | `domain/<agg>/events.py` | an aggregate on state change | use cases of the same context, in-process | same transaction as the command |
| **Integration event** | `application/events.py` | use case on commit | other contexts / external consumers | persisted in `outbox` in the same transaction |

Domain events are internal details; they never leave the process. Integration events are a public contract with version, tenant, correlation id; they go to the bus.

---

## Outbox

Solves the dual-write: the event is written as a row in `outbox` **inside the same transaction** as the command; a separate process publishes it to the bus and marks it as published.

**`outbox` table** (columns): `event_id PK UUIDv7`, `tenant_id`, `event_type`, `event_version`, `aggregate_type`, `aggregate_id`, `payload jsonb`, `occurred_at timestamptz DEFAULT now()`, `correlation_id`, `published_at NULL`, `publish_attempts INT DEFAULT 0`. **No RLS** (the publisher sees all tenants); access restricted by DB role.

```sql
CREATE INDEX idx_outbox_unpublished ON outbox (occurred_at)
  WHERE published_at IS NULL;
```

**Partial** index on `WHERE published_at IS NULL`: the publisher only scans pending rows; published ones do not bloat the index. Non-trivial to infer if rebuilt.

**`processed_events` table** (consumer-side idempotency): PK `(consumer, event_id)`. Insert on processing; `UniqueViolation` = already processed, skip.

---

## Publisher

**MVP**: Lambda in VPC invoked by EventBridge Scheduler every 60 s ([ADR-0007](adr/0007-outbox-dispatch-polling.md)). Drains the outbox on each run; latency ≤ 60 s acceptable for email/audit/counters.

**Post-MVP**: `LISTEN/NOTIFY` from a dedicated Fargate task, with the Scheduler as fallback.

### Algorithm

```python
# Drains the outbox on each Scheduler run
unpublished = SELECT event_id, tenant_id, event_type, event_version,
                     aggregate_type, aggregate_id, payload, occurred_at,
                     correlation_id, publish_attempts
              FROM outbox
              WHERE published_at IS NULL
              ORDER BY occurred_at ASC, event_id ASC
              LIMIT 100

# PutEvents accepts up to 10 entries per call
for batch in chunks(unpublished, 10):
    response = eb.put_events(Entries=[
        {
            "Source": "nica-erp",
            "DetailType": e.event_type,
            "Detail": json.dumps({
                "event_id": e.event_id,
                "event_version": e.event_version,
                "tenant_id": e.tenant_id,
                "aggregate_type": e.aggregate_type,
                "aggregate_id": e.aggregate_id,
                "payload": e.payload,
                "occurred_at": e.occurred_at,
                "correlation_id": e.correlation_id,
            }),
            "EventBusName": "nica-erp",
        }
        for e in batch
    ])
    # Partial errors (FailedEntryCount > 0): inspect each Entry,
    # mark published_at = now() only on successes, publish_attempts++ on failures.
```

Stable order `(occurred_at, event_id)` + `LIMIT 100` avoid starvation. Envelope with fields in that order = **wire contract** for consumers.

### Retries and quarantine

| `publish_attempts` | Behavior |
|---|---|
| 0–4 | Retries on next tick. |
| 5–9 | Exponential backoff with jitter: skips up to `occurred_at + 60s · 2^(attempts-5) + rand(0,30s)`. |
| ≥ 10 | **Poison message**. Alarm `outbox_poisoned_count > 0`. Manual resolution: `scripts/replay-outbox.py --event-id <id>` (resets attempts) or `--drop` (marks published without sending, with reason in log). |

### Ordering and idempotency

EventBridge and SQS standard are not FIFO. Consumers assume arbitrary order and process idempotently (PK in `processed_events`). Future strict ordering: SQS FIFO with `MessageGroupId = aggregate_id` and dedupe by `event_id`; ADR pending if any MVP consumer requires total order. Event versioning (additive vs breaking) is in [ADR-0012](adr/0012-event-versioning.md) — it is independent of ordering.

PK `event_id` UUIDv7 guarantees insert idempotency in `outbox`: transaction retry aborts with PK violation; `event_id` propagates to the bus.

---

## Bus

Custom bus `nica-erp` (not default). Rules to SQS:

- "Notif on InvoiceIssued" → `notif-queue` + DLQ (`maxReceiveCount=5`): `detail-type ∈ {InvoiceIssued, UserRegistered, MemberInvited, LowStockAlerted}`.
- "Audit consume all" → `audit-queue` + DLQ: `source = ["nica-erp"]`.

**256 KB/event limit**: large payloads are truncated keeping key fields, or uploaded to S3 with reference (`s3_bucket`, `s3_key`); consumers hydrate if they need the body.

---

## Consumers (Lambdas SQS)

First step of every handler: read `body["detail"]` (EventBridge serializes as object, not string), `event_id = detail["event_id"]`, `event_type = body["detail-type"]`, `event_version = detail["event_version"]`. Idempotent insert in `processed_events`; `UniqueViolation` → skip. Unhandled exception → SQS redrives; after `maxReceiveCount` → DLQ with alarm. Manual reprocessing with `scripts/replay-dlq.py` (automatic replay aggravates bugs).

---

## Event versioning

`event_version: int`. Additive changes → same `event_version`. Breaking → new `event_version` with parallel handler during transition; consumers route by `(event_type, event_version)`. Detail in [ADR-0012](adr/0012-event-versioning.md).

---

## Idempotent commands (input)

Mutating endpoints accept `Idempotency-Key`. `idempotency_keys` table PK `(tenant_id, key, endpoint)` with `request_hash`, `response_body`, `response_status`, TTL 24 h. Hit → cached response with header `Idempotency-Replayed: true`. Different hash with same key → `409 Conflict`. Detail in [08 § Idempotency-Key](08-api-conventions.md#idempotency-key).

---

## Housekeeping

Lambda `housekeeping_worker` daily at 03:00 America/Managua (= 09:00 UTC, no DST). EventBridge Scheduler cron is expressed in UTC: `cron(0 9 * * ? *)`. Policies configurable via SSM:

| Table | Criterion | Default |
|---|---|---|
| `outbox` | `published_at IS NOT NULL AND published_at < now() - :outbox_retention` | 30 days |
| `processed_events` | `processed_at < now() - :processed_events_retention` | 7 days |
| `idempotency_keys` | `created_at < now() - :idempotency_retention` | 24 h |

`idempotency_keys`: TTL declared in `08-api-conventions.md` (24 h) — housekeeping guarantees `created_at + 24 h` is respected without requiring an `expires_at` column (single source maintained: the SSM default). `DELETE ... LIMIT 10000` in short loops, commit per batch, no prolonged lock. Metric `housekeeping_rows_deleted{table}` via EMF.

At scale (hundreds of small businesses, millions of rows in `outbox`): native partitioning by month → `DROP PARTITION` (instantaneous, no logged WAL) vs `DELETE` (logged and costly).

---

End-to-end diagram in [02 § Invoice issuance flow](02-architecture.md#flow-invoice-issuance-with-outbox).
