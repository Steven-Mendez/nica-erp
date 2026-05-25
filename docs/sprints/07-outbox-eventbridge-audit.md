# Sprint 07 — Outbox publisher + EventBridge + `audit` context + deploy

**Goal.** Outbox events leave to the EventBridge bus (LocalStack in dev, real in AWS), `audit` consumes them and persists append-only. Introduces three Lambdas (`outbox_publisher`, `audit_consumer`, `housekeeping_worker`), custom EventBridge bus, SQS + DLQs. Completes the `EventPublisher` port swap. Here the **canonical Lambda consumer pattern with `processed_events`** that later sprints reuse gets defined.

---

## Dependencies

- [00](00-walking-skeleton.md) (`outbox` table); [03](03-tenants-and-rls.md) (`tenant_id` populated); [05](05-parties-and-sales.md), [06](06-taxes-payments-reports.md) (producers: `InvoiceIssued`, `PaymentReceived`, etc.).
- **Produced here, consumed later**: bus contract (rules, target SQS, DLQs) reused by `notifications_worker` in [08](08-notifications-ses.md).

---

## MVP trade-offs

- **Latency ≤60 s.** `outbox_publisher` runs as a Lambda triggered by EventBridge Scheduler every 60 s. Acceptable for the MVP flows (invoice → transactional email / audit). [ADR-0007](../adr/0007-outbox-dispatch-polling.md) documents upgrade to `LISTEN/NOTIFY` with a Fargate daemon if latency becomes critical.
- **Cost**: ~1440 invocations/day × ~50 ms ≪ 0.01 USD/day. Negligible.

---

## `outbox_publisher` Lambda

`bootstrap/entrypoints/outbox_publisher.py`. Same Docker image as the API; `entrypoint = ["python","-m","bootstrap.entrypoints.outbox_publisher"]`.

1. Connects to DB (creds SSM SecureString `/nica-erp/db/master` via `ssm:GetParameter` + `kms:Decrypt`; [ADR-0021](../adr/0021-ssm-parameter-store.md)).
2. `SELECT event_id, event_type, event_version, aggregate_type, aggregate_id, tenant_id, payload, occurred_at, published_at, publish_attempts FROM outbox WHERE published_at IS NULL ORDER BY occurred_at LIMIT 100`.
3. Batches of 10 (`PutEvents` limit) → `Entries`.
4. Failed entries are not marked (remain for next run).
5. Successful: `UPDATE outbox SET published_at = now(), publish_attempts = publish_attempts + 1 WHERE event_id IN (...)`.
6. `publish_attempts > 10` → log warning (possible poisoning).

Prod: Lambda + EventBridge Scheduler every 60 s (private VPC with RDS access). No long-running daemon.
Local: `make worker-outbox` (loop sleep 2 s), same code.

> **Post-MVP**: `LISTEN/NOTIFY` requires a long-running process and does not fit Lambda; deferred to dedicated Fargate ([ADR-0007](../adr/0007-outbox-dispatch-polling.md)).

---

## `EventPublisherEventBridge` adapter

```python
class EventPublisherEventBridge:
    def __init__(self, client, bus_name: str):
        self._client, self._bus_name = client, bus_name

    async def publish_batch(self, events: list[IntegrationEvent]) -> list[PublishResult]:
        entries = [self._to_entry(e) for e in events]
        resp = await asyncio.to_thread(
            self._client.put_events, Entries=entries, EventBusName=self._bus_name
        )
        return [PublishResult(event_id=e.event_id, ok=r.get("EventId") is not None)
                for e, r in zip(events, resp["Entries"])]
```

`boto3` is synchronous; `asyncio.to_thread` avoids blocking the event loop. `aiobotocore` discarded for simplicity (small batches). Only `outbox_publisher` uses this adapter; use cases write directly to the outbox.

---

## Canonical Lambda consumer pattern (defined here, reused in 08)

1. Receives `event` SQS with batch ≤10 (`event["Records"]`).
2. Per record:
   - `body = json.loads(record["body"])`. `body["detail"]` is already a dict; no second `json.loads` required (see [`../07-events-and-outbox.md`](../07-events-and-outbox.md)).
   - `SELECT 1 FROM processed_events WHERE consumer='<name>' AND event_id=...` → skip if exists.
   - If not: transaction with `INSERT processed_events` + consumer-side domain insert.
3. Partial batch responses: success → message deleted; failure → retry → DLQ after 5 attempts.

Local: `make worker-<name>` (SQS LocalStack polling loop).

---

## `audit/` context

- Aggregate: `AuditLogEntry` (append-only).

```sql
CREATE TABLE audit_log_entries (
  event_id        UUID PRIMARY KEY,        -- same as original event
  tenant_id       UUID NOT NULL,
  event_type      TEXT NOT NULL,
  event_version   INT NOT NULL,
  actor_user_id   UUID,                    -- nullable (may be system)
  entity_type     TEXT NOT NULL,
  entity_id       UUID NOT NULL,
  payload         JSONB NOT NULL,
  correlation_id  UUID,
  occurred_at     TIMESTAMPTZ NOT NULL,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant_occurred ON audit_log_entries(tenant_id, occurred_at DESC);
```

RLS by `tenant_id` (pattern [sprint 03](03-tenants-and-rls.md)).

- Use case: `RecordAuditEntry` (idempotent; UNIQUE on `event_id` deduplicates).
- Query: `ListAuditEntries(filters, cursor)` cursor pagination.

`audit_consumer` implements the canonical pattern above.

---

## EventBridge setup in LocalStack

`docker/localstack-init.sh` creates the bus, queues with redrive policy (`maxReceiveCount=5`), the rule `audit-all` (`source: ["nica-erp"]`) → target `audit-queue`. Full `awslocal` commands in the script. In Terraform `messaging/` the ARNs come from `aws_sqs_queue.audit.arn` (module output); Lambdas receive `LAMBDA_AUDIT_ARN` via env var. No hardcoded ARNs in prod.

`notif-queue` is populated in [sprint 08](08-notifications-ses.md) with a selective event pattern.

---

## Endpoints

`GET /v1/audit-log` — admin of the tenant only. Filters: `actor_user_id`, `entity_type`, `entity_id`, `date_range`, `event_type`. Cursor pagination.

## Migration 0007

`audit_log_entries` with RLS. Additional seed in `permissions` + `role_permissions` (see §Permissions below).

---

## Permissions ([ADR-0022](../adr/0022-rbac-model.md))

| Permission | Resources | Default roles |
|---|---|---|
| `audit-log:read` | `AuditLogEntry` | admin, owner |

`scope='na'` — the audit log has no ownership (it belongs to the tenant, not the actor). Restricted to `admin`/`owner` due to sensitivity: it contains the full trail of actions by all tenant members.

---

## Frontend

Route `/audit/log` with `DataTable` (cursor) + `DatePickerWithRange` + `Combobox` + `Sheet` (drawer with `payload` pretty JSON). Filters persist in URL search params; Zod validation `auditFiltersSchema`. Rest follows README §Shared patterns.

---

## Sprint tests

- Unit: `EventPublisherEventBridge.publish_batch` with boto3 mock (`PutEvents` shape).
- Integration: `outbox_publisher` drains, marks published, does not reprocess; `audit_consumer` idempotent (same event 2× does not duplicate).
- E2E: issue invoice → ~2 s later `outbox.published_at IS NOT NULL` → entry in `audit_log_entries` → `/v1/audit-log` shows it.

---

## Verifiable outcome (local)

```bash
make worker-outbox & make worker-audit &
curl -X POST localhost:8000/v1/invoices/<id>/issue ...
sleep 3
curl 'localhost:8000/v1/audit-log?entity_type=Invoice&entity_id=<id>' ...
# → entry with event_type=sales.InvoiceIssued, full payload, occurred_at, actor_user_id
```

---

## Deploy

Swap `EventPublisher` against real EventBridge + two active Lambdas + daily housekeeping.

### Terraform additions

- **New `messaging/` module**: `nica-erp` EventBridge bus. Rules: `audit-rule` catch-all `nica-erp.*`; `notif-rule` selective (SQS destination populated in [sprint 08](08-notifications-ses.md)). Queues `audit-queue`, `notif-queue` with DLQs `*-dlq`, `maxReceiveCount=5`.
- **`workers/` module extended** (on top of `fx_scraper` from [06](06-taxes-payments-reports.md)):
  - `outbox_publisher`: scheduled rule `outbox_publisher_every_minute` (`rate(1 minute)`).
  - `audit_consumer`: event source mapping from `audit-queue` (batch 10, partial batch responses).
  - `housekeeping_worker`: scheduled `housekeeping_daily` (`cron(0 9 * * ? *)` = 03:00 Managua). DELETE in batches with default retentions: `outbox` 30 days, `processed_events` 7 days, `idempotency_keys` 24 h. Retentions configurable via SSM. Detail in [`../07-events-and-outbox.md` § Housekeeping](../07-events-and-outbox.md#housekeeping) and [ADR-0006](../adr/0006-transactional-outbox.md).
- **IAM**: roles `nica-erp-lambda-{outbox,audit,housekeeping}-role` with `AWSLambdaVPCAccessExecutionRole`, `ssm:GetParameter` + `kms:Decrypt` over `/nica-erp/db/master`, `events:PutEvents` (outbox), `sqs:{ReceiveMessage,DeleteMessage}` (audit).
- **Migration 0007**: `audit_log_entries`, `processed_events` unique `(consumer, event_id)`.
- **EMF metrics**: `outbox_pending_count`, `outbox_published_total`, `outbox_publish_failed_total`, `housekeeping_rows_deleted`, `dlq_depth`. Alarms in [`../10-infrastructure.md` § Metrics](../10-infrastructure.md#business-metrics-emf).

### Wiring

```python
def build_event_publisher() -> EventPublisher:
    if settings.app_env == "local":
        return EventPublisherInProcess(handlers=in_process_handlers)
    return EventPublisherEventBridge(client=boto3.client("events"), bus_name=settings.eventbridge_bus_name)
```

In AWS the use cases only write to the outbox. The Lambda drains every minute and calls `PutEvents`; EventBridge routes to SQS per rules.

### Verifiable outcome post-deploy

See README §Post-deploy verification, plus:
- Issue invoice from UI → wait ≤90 s (60 s scheduler + 5-10 s propagation) → `/audit/log` shows `InvoiceIssued`.
- `aws sqs get-queue-attributes --queue-url <audit-dlq-url> --attribute-names ApproximateNumberOfMessages` → 0.
- Manual drain: `aws lambda invoke --function-name nica-erp-outbox --payload '{}' /tmp/out.json` → `published_count > 0`.
