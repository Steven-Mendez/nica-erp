# ADR-0012 — Event versioning: stable `event_type` + numeric `event_version`

**Status**: Accepted
**Date**: 2026-05-23

## Context
Outbox events ([ADR-0006](0006-transactional-outbox.md)) are a public contract between producer and consumers (`audit_consumer`, `notifications_worker`, future external ones). The schema must be able to evolve without coordinating deploys nor paying for a schema registry for three internal consumers.

## Decision
**Stable `event_type` + `event_version INT NOT NULL` starting at `1`; additive contract within a version.**

- **Within a version**: allowed to add optional fields; forbidden to rename, change types, make an optional field required, or change enum semantics.
- **Breaking change**: bump to `N+1`. Producer publishes **both versions in parallel** for ~30 days (two outbox rows per transaction). New consumers handle `v2`; old ones continue with `v1`. When all migrate, producer stops emitting `v1`.
- **Validation**: per-version Pydantic model in `application/events/<event_name>/v{n}.py`. Producer and consumer validate at the edge.
- **Consumer dispatch**: resolves by `(event_type, event_version)`. Unknown version → log `WARNING event=unknown_event_version` + metric `events_unknown_version_total`; **does not** raise an exception (avoids SQS reingress and DLQ pollution). See [`../07-events-and-outbox.md`](../07-events-and-outbox.md).

## Consequences
- (+) Evolution without coordinating deploys between producer and consumers.
- (+) Auditing: every row and event carries `event_version`; reproduces historical interpretation.
- (+) No extra services: versioning lives in code and one integer column.
- (+) EventBridge rules stay simple (filter by stable `detail-type`).
- (−) Dual publication during the window duplicates events. Acceptable: short window, low volume.
- (−) Additive contract depends on discipline. Mitigated with pending contract tests.
- (−) A consumer stuck on an old version prevents the producer from dropping `v1`. Mitigated with the `events_unknown_version_total` metric.
- (−) Assumes no external consumer joins before the window closes; revisit the policy when the first third-party consumer appears.

## Alternatives
- **Schema registry (Confluent, AWS Glue)** — rejected: over-engineering, ~30 USD/month.
- **Versioning in `event_type`** (`InvoiceIssued.v1`) — rejected: breaks EventBridge rules on every version.
- **Additive evolution without explicit version** — rejected: old consumers break silently.
- **Separate numeric `event_version`** — chosen.

## Revisit triggers
- A third-party / external consumer is onboarded — the 30-day dual-publication window may no longer be enough.
- Number of event types exceeds what manual contract discipline can keep correct (rule of thumb: more than ~30 active types).
