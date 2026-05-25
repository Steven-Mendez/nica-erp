# ADR-0003 — AWS on economy tier with on-demand deploy/destroy

**Status**: Accepted
**Date**: 2026-05-23

## Context
Pre-launch with no productive tenant. The stack must be ready (private VPC, RLS, secrets) but keeping it on 24/7 generates avoidable cost. Goal: functional, secure, and cheap.

## Decision
Minimum tier, brought up on demand during pre-launch. `make deploy` ≈ 12 min, `make destroy` ≈ 10 min, expected sessions of 1–3 days.

Sizing:
- API: ECS Fargate, 1 task `0.25 vCPU / 0.5 GB`.
- DB: RDS PostgreSQL `db.t4g.micro`, single-AZ, gp3 20 GB.
- Network: VPC across 2 AZs (ALB minimum), a single NAT Gateway.
- Auth/email/bus: Cognito Lite, SES, EventBridge/SQS standard.
- No WAF, X-Ray, VPC endpoints, replicas, or Multi-AZ.

Resources persistent across cycles: S3 state, DynamoDB lock, ECR. After [ADR-0020](0020-no-custom-domain-mvp.md) (no custom domain) and [ADR-0021](0021-ssm-parameter-store.md) (SSM instead of Secrets Manager), idle drops from ~$1.80/month to **~$0.02/month**. On-state ≈ $2.70/day. Breakdown in [10 — Infrastructure](../10-infrastructure.md).

## Consequences
- (+) Idle ~$0; predictable session cost.
- (+) IaC discipline: whatever is not in Terraform is lost on destroy.
- (+) A reliable `make destroy` is itself a quality test for the Terraform.
- (−) "Power on → live URL" latency ~12 min.
- (−) Forgetting `make destroy` costs 3–5 USD/day (mitigated with a billing alarm).
- (−) Single-AZ/single-NAT do not tolerate an AZ outage; revisit with the first tenant.

## Alternatives
- **Production tier always on** (Aurora Serverless, redundant NAT, WAF, X-Ray) — rejected: high cost with no revenue.
- **Minimum tier always on** — rejected: ALB + NAT + 24/7 compute still adds up.
- **Minimum tier on demand via `make deploy` / `make destroy`** — chosen.

## Revisit triggers
- First productive tenant onboarded — minimum tier with downtime is no longer acceptable.
- Session frequency rises above a few per week, making the 12 min boot a sustained drag.
- An AZ outage during a session causes a real incident.

Detail in [`../10-infrastructure.md`](../10-infrastructure.md) and [`../11-deployment.md`](../11-deployment.md).
