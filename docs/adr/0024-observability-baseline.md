# ADR-0024 — Observability baseline: structured logs + EMF, no distributed tracing

**Status**: Accepted
**Date**: 2026-05-23

## Context
The system needs three things to be operable: searchable logs, metrics that surface problems before users, and alarms that escalate. Constraints inherited from [ADR-0003](0003-deploy-destroy-per-env.md): low cost, simple to operate, no extra services if AWS-native covers it.

This ADR captures **architectural** decisions about observability — what we measure, what correlates traffic across services, what we explicitly choose *not* to do. Configuration (specific log groups, retention values, alarm thresholds) lives in [`../12-observability.md`](../12-observability.md) and the Terraform `observability/` module.

## Decision
Four architectural commitments:

### 1. Logs are structured JSON, one event per line
`structlog` + `JSONRenderer` produces single-line JSON to stdout, which CloudWatch Logs ingests automatically. Canonical fields on every log line: `timestamp`, `level`, `event`, `tenant_id`, `user_id`, `request_id`, `correlation_id`, plus event-specific fields. **No PII** — names, emails, RUC, phones never appear in logs.

### 2. Metrics travel inside log lines via CloudWatch EMF
[CloudWatch Embedded Metric Format](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html) — metrics ride in the same JSON log line, no separate emit, no agent. Catalog of metrics in [`../12-observability.md`](../12-observability.md). Dimensions are bounded by design: `tenant_id`, `event_type`, `queue`, `document_type` — no high-cardinality dimensions (user_id, correlation_id) become metric labels.

### 3. Correlation IDs replace distributed tracing for MVP
We do not run X-Ray, OpenTelemetry, or any tracing backend. Instead, `correlation_id` (UUIDv7 per [ADR-0011](0011-uuidv7-identifiers.md)) is generated at the edge by an HTTP middleware (reads `X-Correlation-ID` or generates one), then propagated through:

- The outbox table column (`correlation_id`).
- The integration event payload.
- Every log line emitted during the request and its async fan-out.
- The `trace_id` field of any RFC 7807 error response ([ADR-0015](0015-rfc7807-errors.md)).

Operators diagnose multi-service flows with `filter correlation_id = "..."` in CloudWatch Logs Insights.

### 4. Alarms route to SNS, not human channels directly
A single SNS topic (`nica-erp-alerts`) is the integration point. The MVP subscribes email; later subscribers (PagerDuty, Slack) attach without touching the alarm definitions. The SLOs and thresholds themselves live in [`../12-observability.md`](../12-observability.md).

## Consequences
- (+) Marginal cost ≈ $0 — metrics piggyback on logs already paid for.
- (+) No agents, no external services, no licensing.
- (+) `correlation_id` resolves an estimated 80% of multi-service diagnosis without paying for tracing.
- (+) Stack is portable: `structlog`, EMF, future OpenTelemetry SDK are all standards.
- (+) Alarms decoupled from notification mechanism via SNS.
- (−) No tracing — composite latencies are diagnosed by correlation, not by waterfall. Acceptable for current architecture (one ECS service + four Lambdas).
- (−) EMF caps at 100 values per metric per log line; high-cardinality work needs care.
- (−) CloudWatch Logs Insights costs $0.005/GB scanned. Negligible pre-launch.
- (−) Requires discipline — every code path that crosses async boundaries (outbox publisher → SQS → consumer) must thread `correlation_id`. Enforced by lint and code review, not by the runtime.

## Alternatives
- **Datadog / New Relic / Honeycomb** — rejected: ≈ $15/host/month + log-volume scaling, unjustifiable pre-launch.
- **Self-hosted OpenTelemetry + Jaeger/Tempo** — rejected: operating tracing backends is more complexity than value at MVP scale.
- **AWS X-Ray** — rejected: differential value is low with one ECS service and a handful of Lambdas; correlation_id covers the same diagnostic needs.
- **CloudWatch metric filters** (extract metrics from log patterns) — rejected: fragile, limited dimensions, harder to evolve than EMF.
- **`aws-embedded-metrics` library** — considered. Decision: emit EMF as a raw dict inside the `structlog` JSON line rather than introduce a second emitter that might compete for stdout. Re-evaluate if a sprint requires features only the library provides.

## Revisit triggers
- **Cross-service latency complaints** — a flow whose end-to-end latency is opaque under `correlation_id` analysis. Adopt OpenTelemetry SDK + OTel Collector → X-Ray backend.
- **First productive tenant** — re-evaluate retention (currently 7 days; targeting 90 days post-launch).
- **More than 4 Lambdas + 1 ECS service** — tracing's value grows with service count; budget for it earlier.
- **PII regulation forces audit of log content** — review and likely tighten the no-PII rule; consider log redaction at ingest.
- **Alarm fan-out exceeds SNS email** — adopt PagerDuty/Slack subscriptions; alarm definitions stay unchanged.
