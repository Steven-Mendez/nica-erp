# ADR-0004 — ECS Fargate for the API (not Lambda)

**Status**: Accepted
**Date**: 2026-05-23

## Context
Pick an AWS runtime for the FastAPI API.

## Decision
ECS Fargate + uvicorn behind an ALB. 1 task `0.25 vCPU / 0.5 GB`, health check `/healthz`, SQLAlchemy pool `pool_size=5, max_overflow=10`. The async workers (outbox publisher, audit, notifications, fx scraper) do run as Lambdas — spiky, stateless workloads — sharing the same ECR image with a different `entrypoint`.

## Consequences
- (+) No Mangum, no ASGI tricks; behavior matches local `uvicorn`.
- (+) Persistent SQLAlchemy pool without RDS Proxy.
- (−) No scale-to-zero. Compensated by `make destroy` ([ADR-0003](0003-deploy-destroy-per-env.md)).
- (−) ALB costs ~$0.55/day while on.
- (−) Multiple entrypoints in the same image: each workload declares an explicit `command = ["python", "-m", "bootstrap.entrypoints.<name>"]` in its task/lambda definition to avoid silently booting the wrong handler.
- (−) Cold starts ~100–300 ms on the worker Lambdas; tolerable for the publisher (scheduler 60 s, [ADR-0007](0007-outbox-dispatch-polling.md)) and the daily scraper.

## Alternatives
- **Lambda + Mangum + API Gateway** — rejected: Python cold starts and ASGI gotchas via Mangum make local debug diverge from prod.
- **EC2 with uvicorn** — rejected: patches and AMI to maintain.
- **EKS** — rejected: overkill.
- **App Runner** — rejected: no own VPC peering for a private DB, no sidecars.
- **ECS Fargate with uvicorn behind ALB** — chosen.

## Revisit triggers
- Sustained API traffic makes the per-day ALB cost dominate, or scale-to-zero becomes valuable again.
- API workload shape becomes spiky enough that a per-request runtime would be cheaper.
- A second long-running workload appears that could share a container platform — consider whether ECS is still the right fit or another orchestrator pays off.
