# ADR-0007 — Outbox dispatch: 60-second Lambda polling

**Status**: Accepted
**Date**: 2026-05-23

## Context
[ADR-0006](0006-transactional-outbox.md) commits to the outbox pattern for reliable integration events but leaves the dispatch mechanism open. Three families exist:

1. **Polling** — a worker queries the outbox on a schedule. Latency = interval. Simple, no long-lived connections.
2. **`LISTEN/NOTIFY`** — Postgres pub/sub. Latency milliseconds. Requires a worker holding a long-lived DB connection.
3. **Triggers + HTTP callback (`pg_net`)** — Postgres calls out. Anti-pattern: HTTP from inside the DB.

MVP context: deploy/destroy on demand ([ADR-0003](0003-deploy-destroy-per-env.md)), no productive tenants, the events to publish (collections, withholdings, low-stock alerts, signup notifications) tolerate up to ~60 seconds of latency.

## Decision
**Lambda + EventBridge Scheduler, polling the outbox every 60 seconds.** No long-lived connection. Channel name `outbox_publisher`. The publisher reads `WHERE published_at IS NULL ORDER BY occurred_at LIMIT 100`, publishes to EventBridge, marks `published_at = now()` in the same transaction.

The design is forward-compatible with `LISTEN/NOTIFY`: when the upgrade triggers (below) fire, the publisher migrates from a scheduled Lambda to a small Fargate task (0.25 vCPU) holding a `LISTEN outbox_new` connection. The channel carries no payload (only a signal) to dodge the 8 KB `NOTIFY` limit. The outbox table contract does not change.

## Consequences
- (+) MVP simplicity: one Lambda, one EventBridge rule, no persistent processes.
- (+) Lambda cold starts irrelevant at this latency budget.
- (+) Costs ≈ $0 idle (Lambda free tier covers the call frequency).
- (+) The upgrade path is purely additive — no outbox contract change.
- (−) Up to 60s latency between commit and publish. Acceptable for MVP events; documented to stakeholders so a user who issues an invoice and immediately checks their notifications inbox isn't surprised by the delay.
- (−) Lambda cannot hold `LISTEN` long-lived (15-min max, no warm guarantee). Upgrade forces a Fargate worker or a push architecture (SQS FIFO from a trigger).
- (−) Two ways to dispatch (now and future) increase mental load; mitigated by keeping the outbox publisher port the same.

## Alternatives
- **`LISTEN/NOTIFY` from day one** — rejected for MVP: requires a always-on worker (Fargate at $0.50/day minimum), no benefit until latency matters.
- **`pg_net` HTTP from triggers** — rejected: HTTP from inside the DB is an anti-pattern (no transactional rollback, error handling poor).
- **SQS FIFO from a Postgres trigger** — rejected: still requires `pg_net` or an external Lambda triggered by DB activity; no simpler than polling.
- **Debezium / Kafka Connect CDC** — rejected: operational complexity dwarfs the problem.

## Revisit triggers
Concrete signals that promote this to a real upgrade decision:

1. **Latency complaints** — a documented case where the 60s window caused user confusion, OR a UI flow that depends on event-driven update (e.g., live dashboards).
2. **Outbox depth pressure** — sustained > 500 unpublished rows for > 5 minutes at p95, indicating the polling interval can't keep up.
3. **First productive tenant** — re-evaluate whether the latency budget is still 60s under real traffic.
4. **Notification SLA tightens** — an SLA requiring < 10s for any event class.
5. **Throughput > 100 events/minute sustained** — the per-poll batch (100) starts saturating; either increase batch, decrease interval, or move to `LISTEN/NOTIFY`.

When any of these fires, the next ADR moves the publisher to Fargate + `LISTEN/NOTIFY`. Until then, polling stays.
