# ADR-0017 — RDS backups: phase-scoped retention, manual final snapshot, monthly Glacier export

**Status**: Provisional — pre-launch `backup_retention=0` and `skip_final_snapshot=true` make most of this policy inactive. Revisit at first production tenant onboarding (transition to the "First production tenant" phase parameters).
**Date**: 2026-05-23

## Context
The database holds fiscal documents and the audit log; losing them to missing backups is civil liability. Pre-launch the stack is destroyed at the end of each session ([ADR-0003](0003-deploy-destroy-per-env.md)) with no production data, so long automated retention is waste. The strategy must define retention per phase, persistence across `make destroy`, 5-year fiscal coverage without paying 5 years of automated backups, and RPO/RTO.

## Decision
**Parameterize `backup_retention_period` per environment; take a named final snapshot at the first production tenant; export monthly to S3 + Glacier Deep Archive for the fiscal horizon.**

### Phase parameter (`data/` module)

| Phase | `backup_retention_period` | `skip_final_snapshot` | PITR |
|---|---|---|---|
| Pre-launch | `0` | `true` | No |
| First production tenant | `7` | `false` (named snapshot) | Yes (5 min) |
| Stabilization | `35` (max) | `false` | Yes |

Variable changes in `.tfvars`; no module refactor. Documented in [../11-deployment.md §RDS backups](../11-deployment.md#rds-backups).

### Final snapshot
Pre-launch: `skip_final_snapshot=true`, no snapshot or protection — each `make destroy` drops the DB and recreates it with Alembic + seed (~30 s extra). Aligned with idle $0 ([ADR-0020](0020-no-custom-domain-mvp.md)). First production tenant: `skip_final_snapshot=false`, `final_snapshot_identifier="${prefix}-final-${suffix}"` with a timestamp suffix injected from the Makefile to avoid perpetual drift ([../11-deployment.md §RDS backups](../11-deployment.md#rds-backups)); survives `terraform destroy` and is restorable via `snapshot_identifier`.

### Monthly export to S3 + Glacier Deep Archive
Enabled at first production tenant: a monthly EventBridge Scheduled Rule invokes a Lambda `rds_export_worker` that fires `aws rds start-export-task` against the latest snapshot into `nica-erp-rds-exports`; lifecycle to `DEEP_ARCHIVE` after 30 days (~$0.00099/GB/month), expiration > 60 months. Parquet output queryable from Athena for DGI requests without restoring the database.

### RPO/RTO

| Metric | Pre-launch | First production tenant | Stabilization |
|---|---|---|---|
| RPO | ≤ 1 h (manual snapshot) | ≤ 5 min (PITR) | ≤ 5 min |
| RTO | N/A | ≤ 30 min | ≤ 30 min |

Manual DNS cutover: the RDS URL in SSM ([ADR-0021](0021-ssm-parameter-store.md)) is updated and ECS tasks restart.

### Manual restore (runbook in [13 — Operations](../13-operations.md#restore-from-backup))

1. **From automated snapshot**: `terraform apply` with `snapshot_identifier="rds:nica-erp-..."`.
2. **PITR**: `aws rds restore-db-instance-to-point-in-time` + cutover.
3. **From S3 export**: Athena for DGI requests; not for operational recovery.

### Encryption
Snapshots inherit the RDS storage KMS key; S3 exports use SSE-S3 or KMS depending on bucket ([../11-deployment.md §Encryption at rest](../11-deployment.md#encryption-at-rest)).

## Consequences
- (+) Cost scales by phase: zero pre-launch; negligible at 35 days.
- (+) Fiscal horizon in Glacier Deep Archive for cents (5 GB ≈ $0.005/month).
- (+) 5-minute PITR recovers an accidental drop with minimal loss.
- (+) Final snapshot decouples `make destroy` from data loss risk.
- (+) Athena/Parquet restore answers DGI without bringing up an archive RDS.
- (−) Phase change is a manual intervention with checklist.
- (−) Monthly export needs an extra Terraform module (`storage/` or `backup/`); not included in MVP sprints 00-09, ships with the first productive tenant.
- (−) 30-minute RTO assumes an operator is available; with production tenants an on-call runbook is required.
- (−) Glacier Deep Archive: 12-48 h retrieval latency. Acceptable for DGI.
- (−) Assumes `aws rds start-export-task` is supported on RDS PostgreSQL 16; verify before enabling the monthly export at first productive tenant.

## Alternatives
- **Manual final snapshot only** — fragile in production (no PITR).
- **Fixed 7-day retention** — does not cover 5 years; wasteful pre-launch.
- **Aurora Backtrack** — rejected: Aurora MySQL only.
- **Cross-region backup** — rejected: regional DR is not an MVP requirement.
- **35-day retention + monthly S3 Glacier export** — chosen.

## Revisit triggers
- First production tenant onboarded — switch to the production phase parameters.
- DGI extends or changes the fiscal retention horizon beyond 5 years.
- Regional DR becomes a contractual requirement.
- `aws rds start-export-task` ceases to be supported on the running PostgreSQL version.
