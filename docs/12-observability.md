# 12 — Observability

Operational visibility: structured logs, metrics, alarms, dashboards, and the queries used to debug. Architectural commitments live in [ADR-0024](adr/0024-observability-baseline.md); this document is the **how**.

---

## Stack

- **Logs**: CloudWatch Logs (one log group per service); JSON via `structlog`.
- **Metrics**: CloudWatch Metrics via CloudWatch [Embedded Metric Format (EMF)](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html). Metrics ride in the same JSON log line — no second sink.
- **Dashboards**: CloudWatch Dashboards (`pyme-erp-overview`, sprint-specific dashboards).
- **Alarms**: CloudWatch Alarms → SNS topic `pyme-erp-alerts` → email (MVP). PagerDuty/Slack subscriptions are post-MVP.
- **Tracing**: none in MVP. `correlation_id` propagation replaces it ([ADR-0024](adr/0024-observability-baseline.md)).

---

## Log schema

Every log line is single-line JSON. Canonical fields on every event:

```json
{
  "timestamp": "2026-05-23T14:32:11.456Z",
  "level": "info",
  "event": "invoice.issued",
  "tenant_id": "01HZ8XKJ4...",
  "user_id": "01HZ8XKJ...",
  "request_id": "01HZ8XK...",
  "correlation_id": "01HZ8XK..."
}
```

Event-specific fields are added per call site. Never log:
- Names, emails, RUCs, phone numbers, addresses (PII).
- JWTs, refresh tokens, passwords, signing keys.
- Full payloads of fiscal documents (just the IDs and amounts).

`structlog` is configured with a processor that strips known PII fields by name as a safety net.

### Retention
- Pre-launch: **7 days** across all log groups.
- First productive tenant: **90 days** for API and audit; **30 days** for the rest.

---

## Metrics catalog

Each metric below has dimensions in parentheses. EMF emits them inside the relevant log line.

### Platform metrics

| Metric | Dimensions | Source | Why |
|---|---|---|---|
| `api.request.count` | `route`, `status_code`, `tenant_id` | FastAPI middleware | Per-endpoint traffic, error rate |
| `api.request.duration_ms` | `route`, `status_code` | FastAPI middleware | p50, p95, p99 per endpoint |
| `db.query.duration_ms` | `repository` | SQLAlchemy event hook | Slow query detection |
| `outbox.pending_count` | (none) | Outbox publisher | Backpressure signal |
| `outbox.published_total` | `event_type` | Outbox publisher | Throughput |
| `outbox.publish_duration_ms` | (none) | Outbox publisher | Dispatch health |
| `dlq.depth` | `queue` | EventBridge/SQS via Lambda metric | Consumer failure signal |
| `lambda.cold_start_count` | `function_name` | Lambda extension | Cold start frequency |

### Business metrics

| Metric | Dimensions | Source | Why |
|---|---|---|---|
| `invoice.issue_duration_ms` | `tenant_id` | `IssueInvoice` use case | UX-critical operation |
| `number_sequence.remaining_pct` | `tenant_id`, `doc_type` | `NumberSequence` lookup | Heads-up before exhaustion |
| `tax.calculation_duration_ms` | `tenant_id` | `TaxCalculator` | Detect N+1 regression |
| `payment.applied_total` | `tenant_id` | `ApplyPayment` use case | Activity signal |
| `notification.sent_total` | `event_type` | `notifications_worker` | Throughput |
| `notification.send_duration_ms` | `event_type` | `notifications_worker` | SES latency |

Dimensions are bounded by design: `tenant_id`, `event_type`, `route`, `queue`, `document_type`, `function_name`. **Never** `user_id`, `correlation_id`, `customer_id`, `product_id` — they cause metric cardinality explosion.

---

## Alarms

Defined in the Terraform `observability/` module. All notify `pyme-erp-alerts` SNS topic.

| Alarm | Condition | Action |
|---|---|---|
| `api-5xx-rate-high` | `api.request.count{status_code=5xx}` > 1% of total over 5 min | Investigate API logs by `correlation_id` |
| `api-latency-p95-high` | `api.request.duration_ms` p95 > 2s over 5 min | Check slow query metric; check RDS CPU |
| `outbox-depth-high` | `outbox.pending_count` > 500 sustained > 5 min | Outbox publisher Lambda failing or slow |
| `dlq-depth-positive` | `dlq.depth` > 0 over 1 min | Consumer poison message — review DLQ |
| `lambda-errors` | Any Lambda errors > 0 over 5 min | Check function logs |
| `rds-cpu-high` | RDS CPU > 80% sustained > 10 min | Identify slow query; scale or optimize |
| `rds-storage-low` | Free storage < 5 GB | Resize storage |
| `number-sequence-low` | `number_sequence.remaining_pct` < 10% | Provision next series |
| `billing-monthly` | AWS billing > $20 pre-launch / per-tenant cap post-launch | Cost audit |

Each alarm doc-comment in Terraform names the runbook section in [13 — Operations](13-operations.md).

---

## Dashboards

### `pyme-erp-overview`
- ALB requests/s (last 1h)
- API p50, p95, p99 latency (last 1h)
- RDS CPU, memory, free storage (last 6h)
- Outbox pending depth (last 6h)
- DLQ depth across all queues (last 24h)
- Lambda invocation count + error count per function (last 24h)

### Per-sprint dashboards
Added when a sprint introduces a new high-leverage metric — e.g., sprint 06 adds a Taxes panel (IR accumulation runtime, withholding count), sprint 08 adds a Notifications panel (SES send rate, bounce rate).

---

## Correlation IDs

`correlation_id` is the spine that replaces distributed tracing in MVP.

### Lifecycle
1. **HTTP edge**: middleware reads `X-Correlation-ID` from the request, or generates a UUIDv7 ([ADR-0011](adr/0011-uuidv7-identifiers.md)) if absent.
2. **Bound to logging context**: every log line emitted during this request carries it via `structlog.contextvars`.
3. **Persisted to outbox**: the `outbox_events.correlation_id` column captures it on write.
4. **Propagated to event payload**: integration events carry it in their envelope.
5. **Re-bound in consumers**: SQS/EventBridge consumers read it from the message and rebind to their logging context.
6. **Exposed in errors**: RFC 7807 error responses include it as `trace_id` ([ADR-0015](adr/0015-rfc7807-errors.md)).

### Querying

CloudWatch Logs Insights query templates (saved):

```
fields @timestamp, level, event, tenant_id, user_id
| filter correlation_id = "01HZ..."
| sort @timestamp asc
```

```
fields @timestamp, level, event, @message
| filter tenant_id = "<id>" and level in ["error", "warning"]
| sort @timestamp desc
| limit 100
```

```
fields @timestamp, event, route, status_code, duration_ms
| filter status_code >= 500
| stats count() by route, status_code
```

More queries in [13 — Operations §Debug runbook](13-operations.md#debug-runbook).

---

## Writing logs (for contributors)

### Per-event fields

Auto-injected by the structlog middleware — **do not add manually**: `timestamp`, `level`, `request_id`, `correlation_id`, `tenant_id`, `user_id`.

Add what makes the event debuggable: IDs (`invoice_id`, `payment_id`), counts (`items_count`), durations (`duration_ms`), document types.

```python
# Good — structured, queryable in Logs Insights
logger.info(
    "invoice.issued",
    invoice_id=str(invoice.id),
    document_type=invoice.document_type,
    total_cents=invoice.total.amount_cents,
    duration_ms=duration_ms,
)

# Bad — unstructured, untraceable
logger.info(f"Issued invoice {invoice.id} for {invoice.total} in {duration_ms}ms")
```

### Levels

| Level   | Use for                                                              |
| ------- | -------------------------------------------------------------------- |
| `debug` | Per-operation detail (cache hits, query plans). Off in production.   |
| `info`  | Business events (`invoice.issued`, `payment.applied`).               |
| `warn`  | Recoverable problems (retry succeeded, fell back to default).        |
| `error` | Failures the user notices. Always include `exc_info=True`.           |

### Never log

- PII: names, emails, RUCs, phone numbers, addresses.
- Secrets: JWTs, refresh tokens, passwords, signing keys.
- Full fiscal document bodies — IDs and totals only.
- `print()`. Use `logger.debug(...)`.
- f-string formatting **of the message** — use structured fields so CloudWatch Logs Insights can query them.

---

## What is not measured

Explicit non-goals:
- **APM agents** — Datadog/New Relic etc. Reconsidered at first productive tenant.
- **Distributed tracing waterfalls** — adopted only after a correlation_id-driven investigation fails to explain a latency complaint.
- **Per-user metrics** — high cardinality, no operational use today.
- **Synthetic monitoring (Pingdom-style)** — `/healthz` + ALB target health is enough for MVP traffic patterns.

---

## References
- [ADR-0024](adr/0024-observability-baseline.md) — architectural commitments
- [ADR-0011](adr/0011-uuidv7-identifiers.md) — correlation_id format
- [ADR-0015](adr/0015-rfc7807-errors.md) — `trace_id` in error responses
- [13 — Operations](13-operations.md) — runbooks the alarms point to
- [10 — Infrastructure](10-infrastructure.md) — where log groups and alarms are provisioned
