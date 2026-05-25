# 13 — Operations

Runbooks. One section per operational scenario. Each runbook is callable from an alarm or a support ticket and is updated when it gets executed.

This is a living document — when a scenario plays out, the operator updates the runbook with whatever was actually true.

---

## Index

- [Debug runbook](#debug-runbook) — generic "something looks wrong" flow
- [Incident response](#incident-response) — P1/P2 severity playbook
- [Restore from backup](#restore-from-backup) — RDS PITR + snapshot restore
- [JWT key rotation](#jwt-key-rotation) — suspected leak of `/pyme-erp/jwt/signing-key`
- [Tenant operations](#tenant-operations) — suspend, reactivate, purge
- [Outbox poison message](#outbox-poison-message) — DLQ depth > 0
- [Data migration runbook](#data-migration-runbook) — multi-phase migrations
- [Cost spike investigation](#cost-spike-investigation) — billing alarm triggered
- [Disaster recovery drill](#disaster-recovery-drill) — periodic verification

---

## Debug runbook

When an alarm fires or a user reports an issue, work through this in order. Stop at the first step that explains the symptom.

1. **Open the SNS-linked alarm**. Note the metric, threshold, and time window.
2. **CloudWatch Dashboard `pyme-erp-overview`** — eyeball the same time window for adjacent anomalies (CPU spike, latency rise, DLQ depth).
3. **Logs Insights** — start with the all-errors query in [12 — Observability §Querying](12-observability.md#querying), narrow by `tenant_id` or `correlation_id`.
4. **If you have a `correlation_id`** (from a user-reported error containing `trace_id`):
   ```
   fields @timestamp, level, event, tenant_id, user_id, @message
   | filter correlation_id = "<id>"
   | sort @timestamp asc
   ```
   This pulls the full request fan-out across the API and any async consumers.
5. **If you don't have a correlation_id** (the symptom is "things are slow"):
   - Check `api.request.duration_ms` p95 by `route` over the time window.
   - Check `db.query.duration_ms` by `repository` — slowest first.
   - Check RDS CPU and free storage.
6. **Confirm root cause** before acting. Don't restart, scale, or rotate unless the data supports it.

---

## Incident response

Severity definitions:

| Severity | Definition | Response time |
|---|---|---|
| **P1** | Customer-visible outage, data loss risk, or compliance breach | Immediate; drop other work |
| **P2** | Significant degradation, no data loss | Same day |
| **P3** | Minor issue, workaround exists | Next sprint |

### P1 flow
1. **Acknowledge** the alarm in SNS (manual reply or runbook automation).
2. **Communicate** — notify affected tenants via the status channel (post-MVP) or email.
3. **Stop the bleeding** — feature flag off, scale up, fail over, whatever drops impact fastest.
4. **Diagnose** — debug runbook.
5. **Fix** — usually in a follow-up PR; the immediate action is mitigation.
6. **Post-mortem within 7 days** — `docs/incidents/YYYY-MM-DD-slug.md` (created when needed). What broke, why, what we changed, what we'll change.

Pre-launch, the dev is on call. Once productive tenants exist, the on-call rotation is defined in [ADR-0029](adr/0029-disaster-recovery-posture.md).

---

## Restore from backup

Per [ADR-0017](adr/0017-backups-pitr.md).

### From PITR (within retention window)
1. Pick the target time (just before the incident).
2. ```bash
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier pyme-erp \
     --target-db-instance-identifier pyme-erp-restore-$(date +%Y%m%d) \
     --restore-time <ISO8601> \
     --db-subnet-group-name pyme-erp-private
   ```
3. Verify on the restored instance: row counts on key tables, last fiscal number, RLS works (`SET app.tenant_id = '...'` then a SELECT).
4. **Cutover**: point the API task definition at the new endpoint via SSM, redeploy ECS service.
5. Keep the original instance for 24h before deletion (in case the restore was wrong).

### From snapshot
1. ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier pyme-erp-restore-$(date +%Y%m%d) \
     --db-snapshot-identifier <snapshot-id>
   ```
2. Continue from step 3 above.

### From Glacier archive (rare, > 35-day-old data)
1. Initiate Glacier restore on the archived snapshot (4-12h retrieval window for Deep Archive).
2. Once available, follow the snapshot restore flow.
3. Document the request — `ops/glacier-restores.md` (created when needed).

---

## JWT key rotation

Per [06 — Security model §Rotation](06-security-model.md#rotation). Trigger: suspected leak of `/pyme-erp/jwt/signing-key`.

1. **Generate** a new key:
   ```bash
   NEW_KEY=$(openssl rand -hex 32)
   ```
2. **Update SSM**:
   ```bash
   aws ssm put-parameter \
     --name /pyme-erp/jwt/signing-key \
     --value "$NEW_KEY" \
     --overwrite \
     --type SecureString
   ```
3. **Force ECS redeploy** to pick up the new key:
   ```bash
   aws ecs update-service \
     --cluster pyme-erp \
     --service api \
     --force-new-deployment
   ```
4. **Verify** — `/healthz` returns 200; a fresh login succeeds; an old token returns 401.
5. **Log the incident** in `docs/incidents/YYYY-MM-DD-jwt-rotation.md`.

All existing sessions are invalidated. This is the intended effect.

---

## Tenant operations

Per [ADR-0026](adr/0026-tenant-lifecycle.md) state machine.

### Suspend a tenant
Trigger: non-payment, abuse, or owner request.

1. **Verify** the request (owner consent recorded, or operational decision documented).
2. Update `tenants.status`:
   ```sql
   UPDATE tenants SET status = 'suspended', suspended_at = now()
   WHERE id = '<tenant_id>';
   ```
3. Emit `TenantSuspended` event via outbox (insert into `outbox_events`).
4. Notify the owner via email (template in `notifications_worker`).
5. Confirm: a request from a tenant user returns `403 problem+json` with `type=tenant-suspended` within 60s (the next request after the tenant context dependency reloads).

### Reactivate a tenant
1. Confirm the suspension reason is resolved.
2. ```sql
   UPDATE tenants SET status = 'active', suspended_at = NULL
   WHERE id = '<tenant_id>';
   ```
3. Emit `TenantReactivated`.
4. Notify the owner.

### Purge a tenant (irreversible)
Preconditions:
- Tenant has been `suspended` for the legal retention window (5 years per DGI).
- Owner has signed a purge consent (stored outside the system).
- Backup snapshot of the tenant's data is moved to `retention/legal-hold/` before purge starts.

Steps:
1. Final snapshot to legal hold: `aws rds create-db-snapshot` → tag with `tenant_id`, `purpose=legal-hold`.
2. Run the purge script (batched, watchdog timeout): `make purge-tenant TENANT_ID=<id>`.
3. Verify: `SELECT COUNT(*) FROM <each tenant-scoped table> WHERE tenant_id = '<id>'` returns 0.
4. Update `tenants.status = 'purged'`, `purged_at = now()`. Row stays for audit.
5. Emit `TenantPurged`.
6. Document in `docs/incidents/YYYY-MM-DD-tenant-purge.md`.

---

## Outbox poison message

Trigger: `dlq-depth-positive` alarm.

1. **Inspect** the DLQ message:
   ```bash
   aws sqs receive-message \
     --queue-url <dlq-url> \
     --max-number-of-messages 1 \
     --message-attribute-names All
   ```
2. **Identify** the failing consumer and event from the message body and `correlation_id`.
3. **Reproduce** locally with a unit test using the message payload.
4. **Fix** the consumer code. Deploy.
5. **Replay** the message:
   ```bash
   aws sqs send-message --queue-url <main-queue-url> --message-body "$(...)"
   ```
6. **Verify** the consumer processes successfully.
7. **Delete** the original DLQ message.
8. Log to incident file if this affected > 1 tenant or recurred.

---

## Data migration runbook

Per [ADR-0028](adr/0028-data-migration-strategy.md). For multi-phase migrations (Rename, Type change, Backfill).

### Backfill
1. **Add** the column nullable + dual-write in code. Deploy.
2. **Run** the backfill script as a one-off ECS task:
   ```bash
   make backfill SCRIPT=backfill_<name>
   ```
3. **Verify** completeness: `SELECT COUNT(*) FROM table WHERE new_col IS NULL` returns 0.
4. **Flip** the constraint to `NOT NULL` in a new migration. Deploy.

### Rename
1. **Add** the new column + dual-write + read-new in code. Deploy.
2. **Wait** at least one full deploy cycle to confirm no errors.
3. **Drop** the old column in a new migration. Deploy.

If anything goes wrong between phases, roll forward — never roll back a partial schema. `downgrade()` exists for local dev cycles, not for prod rollback.

---

## Cost spike investigation

Trigger: `billing-monthly` alarm.

1. **Cost Explorer** — filter by `Project=pyme-erp`, group by **Service**, daily granularity, last 14 days.
2. Identify the service driving the spike.
3. Common causes:
   - **NAT data transfer** — unexpected outbound traffic from Lambda or ECS. Inspect VPC flow logs.
   - **CloudWatch Logs ingestion** — log volume jumped (e.g., a tight loop logging at INFO). Reduce log level or fix the loop.
   - **RDS storage growth** — table grew faster than expected. Identify with `pg_total_relation_size`.
   - **S3 PUT/GET volume** — image upload spam, log dumping, runaway backup.
4. Mitigate immediately (kill the loop, throttle, gate). Fix root cause in a PR.
5. Document in `docs/incidents/YYYY-MM-DD-cost-spike.md`.

---

## Disaster recovery drill

Per [ADR-0029](adr/0029-disaster-recovery-posture.md). Cadence depends on phase.

### Drill protocol
1. Pick RPO target: `now() - <phase_RPO>`.
2. Restore RDS to a sandbox account/VPC (`restore-db-instance-to-point-in-time`).
3. Verify (10-minute timer):
   - Row counts on key tables match expected within tolerance.
   - Last fiscal number recovered (`SELECT MAX(next_number) FROM number_sequences`).
   - RLS works (`SET app.tenant_id = ...` then SELECT returns rows).
   - Application boots cleanly against the restored DB (deploy a throwaway API task).
4. Record elapsed time. Compare to RTO target.
5. Tear down the sandbox: `terraform destroy` on the drill workspace.
6. Log the drill in this doc:

   ```
   ### Drill log
   | Date | Phase | RPO target | RTO target | Actual RTO | Issues | Owner |
   |---|---|---|---|---|---|---|
   | 2026-MM-DD | pre-launch | ∞ | ∞ | 18 min | none | <dev> |
   ```

A failed drill is a P1 — fix the gap before the next sprint closes.

---

## Drill log

(Empty — populated as drills happen.)

| Date | Phase | RPO target | RTO target | Actual RTO | Issues | Owner |
|---|---|---|---|---|---|---|

---

## References
- [ADR-0017](adr/0017-backups-pitr.md) — backup mechanics
- [ADR-0026](adr/0026-tenant-lifecycle.md) — tenant state machine
- [ADR-0028](adr/0028-data-migration-strategy.md) — migration shapes
- [ADR-0029](adr/0029-disaster-recovery-posture.md) — DR posture per phase
- [12 — Observability](12-observability.md) — alarms that drive these runbooks
- [06 — Security model](06-security-model.md) — auth and authz context for tenant ops
