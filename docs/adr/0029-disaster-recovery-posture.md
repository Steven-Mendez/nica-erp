# ADR-0029 — Disaster recovery posture

**Status**: Accepted
**Date**: 2026-05-23

## Context
[ADR-0017](0017-backups-pitr.md) defines RDS backup mechanics (PITR, manual snapshots, Glacier archive). What's missing: the **posture** — RTO/RPO commitments per phase, what disasters are in scope, who runs the recovery, and what tests prove it works. Without this, "we have backups" is a story, not a guarantee.

## Decision
**Three phases, three postures.** Each phase tightens commitments as risk rises. Runbooks live in [`../13-operations.md`](../13-operations.md).

### Phases and commitments

| Phase | RPO | RTO | Backup retention | Tested how |
|---|---|---|---|---|
| **Pre-launch** (current) | ∞ (any loss acceptable) | ∞ | None (`skip_final_snapshot = true`) | Manual restore proven once per ADR-0017 sprint |
| **First productive tenant** | ≤ 5 min | 4 hours | 7-day PITR + weekly snapshots ([ADR-0017](0017-backups-pitr.md)) | Quarterly restore drill in a separate AWS account |
| **Multi-tenant production** | 1 hour | 1 hour | 35-day PITR + monthly snapshot to Glacier Deep Archive | Monthly automated restore drill + annual full DR exercise |

### What's in scope
- **Region-wide AWS outage in `us-east-1`** — accepted risk in MVP (single region). Mitigation: cross-region snapshot copy starting at first productive tenant.
- **RDS instance failure** — Multi-AZ standby starting at first productive tenant; single-AZ accepted pre-launch.
- **Data corruption** (logical, not physical) — PITR restore to a point before the corruption.
- **Tenant deletion in error** — restore from snapshot to a new RDS instance, extract the tenant's rows, reimport. Documented runbook.
- **Accidental `terraform destroy`** — covered by the deploy/destroy model ([ADR-0003](0003-deploy-destroy-per-env.md)); pre-launch RPO of ∞ makes this a known trade.

### What's out of scope
- **Multi-region active-active.** Cost and complexity exceed the SMB market value for years.
- **Cross-cloud DR** (AWS → GCP). Not a relevant risk class.
- **DR for the SPA bundle.** S3 versioning + CloudFront caching make recovery a redeploy.

### Ownership
- **Pre-launch**: one dev. The dev runs the manual restore drill at the end of each sprint that touches RDS schema.
- **First productive tenant**: still one dev, but the quarterly drill is calendared and logged in [`../13-operations.md`](../13-operations.md).
- **Multi-tenant**: on-call rotation. DR drill is part of on-call onboarding.

### Drill protocol
Each drill:
1. Picks a target RPO point (`now() - <RPO>`).
2. Restores to a new RDS instance in a sandbox account/VPC.
3. Verifies — row counts match within tolerance, last fiscal sequence number recovered, RLS still works, application boots.
4. Tears down the sandbox.
5. Records duration vs RTO and any issues in `docs/13-operations.md` drill log.

Failure of any drill is a P1 — block all non-critical work until resolved.

## Consequences
- (+) Posture scales with risk, not all-or-nothing.
- (+) Pre-launch ∞/∞ posture is honest — no false claims about resilience that don't exist yet.
- (+) Runbooks are the artifact, not Confluence pages; lives in the repo.
- (+) Drill cadence is explicit and verifiable.
- (−) Pre-launch posture means a corrupt schema migration could lose everything. Mitigation: [ADR-0028](0028-data-migration-strategy.md) requires reversible migrations and the rolling-deploy gates ([ADR-0018](0018-rolling-deploys.md)) catch breakage early.
- (−) Cross-region copies are unbudgeted pre-launch. First productive tenant must include an explicit cost estimate.
- (−) On-call rotation isn't real until headcount supports it; until then, one dev = single point of failure for response.

## Alternatives
- **Cold backups only, no PITR ever** — rejected: cheap but RPO of 24h is uncompetitive once revenue depends on uptime.
- **Pilot light architecture in `us-west-2`** — rejected at MVP: cost/complexity not justified, but a candidate for "multi-tenant production" phase.
- **AWS Backup managed service** — considered for the multi-tenant phase. Single-pane backups across services. Not in MVP because RDS snapshots cover the only stateful resource.
- **Cassandra/DynamoDB global tables instead of RDS** — rejected: re-architects everything around a problem we don't have.

## Revisit triggers
- **First productive tenant signs a contract** — promote to "First productive tenant" phase before go-live. RPO/RTO commitments become contractual.
- **Region-wide AWS outage hits even without us being affected** — re-evaluate cross-region cost vs probability.
- **A drill fails** — root-cause and tighten the runbook before next drill.
- **Headcount reaches 3+** — formalize on-call.
- **Tenant data > 100 GB** — restore time grows beyond RTO budgets; investigate streaming restore or pre-provisioned standby.
