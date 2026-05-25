# ADR-0020 — No custom domain: AWS default URLs across the pre-launch stack

**Status**: Accepted
**Date**: 2026-05-23

## Context
Pre-launch there are no public URL commitments. Analyzing idle cost under [ADR-0003](0003-deploy-destroy-per-env.md) shows 96% of the cost comes from custom domain + secrets (Route 53 hosted zone $0.50/month + Secrets Manager × 3 $1.20/month + final snapshot $0.05/month + S3 state/DynamoDB/ECR $0.02/month = **~$1.77/month**). On top of that, the custom domain introduces gotchas when recreating after `make wipe`: hosted zone destroyed → new NS → manual update at the registrar → 1-48 h propagation; ACM cert recreated → new DNS validation. Unjustified overhead for sporadic demos.

## Decision
**The entire stack runs on AWS default URLs until the first production tenant.**

### Topology

| Resource | Pre-launch URL |
|---|---|
| Frontend (SPA) | `https://<dist-id>.cloudfront.net/` |
| Backend API | `https://<dist-id>.cloudfront.net/api/*` |
| Cognito user pool domain (OAuth endpoints) | `https://pyme-erp.auth.us-east-1.amazoncognito.com` (Hosted UI **not** used; MVP authenticates via `USER_PASSWORD_AUTH`) |
| SES sender | `noreply@<verified-email>` (sandbox) |

The SPA uses the relative path `VITE_API_BASE_URL=/api`; it does not hardcode the CloudFront URL.

### CloudFront as the single front-door
- Default behavior `/*` → S3 (SPA).
- Behavior `/api/*` → ALB (origin protocol http-only), TTL=0, forward `Authorization` + `Cookie`.
- TLS termination at CloudFront (free `*.cloudfront.net` cert).
- ALB in plain HTTP :80; security group restricted to the managed prefix list `com.amazonaws.global.cloudfront.origin-facing` to block bypass.
- Same origin SPA + API → **no CORS**; session cookies without `SameSite=None`.

### Cognito user pool domain
- `aws_cognito_user_pool_domain` with prefix `pyme-erp`; no custom domain. It enables the OAuth endpoints (`/oauth2/token`, JWKS) and remains available if Hosted UI is activated later; the MVP does not use it (`USER_PASSWORD_AUTH` flow from the API).
- Callback/logout URLs read `aws_cloudfront_distribution.main.domain_name` in Terraform — declared for future OAuth flows, unused in MVP.

### SES permanent sandbox
- Without a domain we cannot verify domain identities (DKIM/SPF) — only email identities (1 operator address for demos; ≤ 50 verified manually).
- **No attempt to exit sandbox**: AWS approval without DKIM/DMARC has a low success rate.
- Sprint planning is simplified; the demo sprint removes "exit SES sandbox" from the DoD.

### Reduced persistent resources

| Category | Before | After |
|---|---|---|
| S3 state + DynamoDB + ECR | $0.02/month | $0.02/month |
| RDS final snapshot | $0.05/month | **no** ([ADR-0017](0017-backups-pitr.md)) |
| Route 53 hosted zone | $0.50/month | **no** |
| Secrets Manager × 3 | $1.20/month | **no** ([ADR-0021](0021-ssm-parameter-store.md)) |
| **Idle total** | **~$1.77/month** | **~$0.02/month** |

`make wipe` + re-bootstrap becomes trivial: no NS records, no secrets in recovery window, no orphan snapshots.

## Consequences
- (+) Idle ≈ $0/month. Meets "easy to destroy in its entirety".
- (+) `make wipe` + re-bootstrap with no surprises; no external state to coordinate.
- (+) No CORS: frontend and API share an origin; session cookies are simple.
- (+) Automatic free HTTPS via `*.cloudfront.net`.
- (+) Single URL to share at demos.
- (+) Permanent CloudFront free tier (1 TB egress + 10M req/month) covers demos.
- (−) "Ugly" URL (`https://d1a2b3c4.cloudfront.net`). Acceptable with no clients or marketing.
- (−) URL changes after `make wipe` (new distribution). Everything is in Terraform; callbacks and SPA update in the same apply.
- (−) SES sandbox limits recipients. For real prospects: verify manually, or register a domain and revert this ADR.
- (−) CloudFront in front of the ALB adds ~20-50 ms first byte. Acceptable.
- (−) Cannot use `<app|api>.mycompany.dev` for demos to stakeholders expecting a professional URL.
- (−) Reverting to custom domain requires a dedicated sprint (see below).

## Reversion plan to custom domain

When the first production tenant appears:

- Register the domain via Route 53 Registrar (avoids the NS gotcha); `aws_route53_zone` becomes a persistent resource again.
- ACM certs (`us-east-1`) for `app.<domain>` and `api.<domain>` with automatic DNS validation.
- CloudFront `aliases` + cert; keep the single front-door or split `api.<domain>` with dedicated HTTPS on the ALB.
- Cognito custom domain `auth.<domain>` + cert; SES domain identity with DKIM in Route 53; out-of-sandbox ticket.
- Update Cognito callback URLs + `VITE_API_BASE_URL`; mark this ADR as Superseded by the new one.

Estimated cost: 1 sprint, ~$15 first-year setup (domain) + $1.77/month recurring idle.

## Alternatives
- **Custom domain** (original implicit decision) — rejected: idle cost + recreate gotchas.
- **Buy domain via Route 53 Registrar** (~$15/year) — rejected: removes the NS gotcha but keeps hosted zone + ACM cost with no pre-launch value.
- **AWS default URLs** — chosen: CloudFront default, Cognito user pool domain with default prefix (no Hosted UI), SES sandbox email-only.

## Revisit triggers
- First production tenant onboarded — execute the reversion plan.
- A stakeholder demo requires a branded URL.
- AWS deprecates `*.cloudfront.net` HTTPS for default distributions.
- SES recipient cap becomes a blocker for legitimate verification flows.
