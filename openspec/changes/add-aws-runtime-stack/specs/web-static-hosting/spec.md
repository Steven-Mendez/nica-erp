## MODIFIED Requirements

### Requirement: CloudFront declares two behaviors with an `/api/*` placeholder origin

The distribution SHALL declare exactly two behaviors:

- **Default `/*` behavior** SHALL target the `nica-erp-web` origin via
  OAC, allowed methods `GET, HEAD, OPTIONS`, cached methods
  `GET, HEAD`, `ViewerProtocolPolicy=redirect-to-https`, and the
  AWS managed cache policy `CachingOptimized`.
- **Path-pattern `/api/*` behavior** SHALL be present with allowed
  methods `GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE`,
  `ViewerProtocolPolicy=redirect-to-https`, AWS managed cache policy
  `CachingDisabled`, AWS managed origin-request policy
  `AllViewerExceptHostHeader`, and a custom HTTP-only origin whose
  `DomainName` is determined by the deployment lifecycle:
  - **Before `add-aws-runtime-stack` apply**: `DomainName` SHALL be
    `placeholder.invalid` (the bootstrap-time default), and
    `GET /api/*` requests SHALL surface an HTTP 5xx CloudFront origin
    error.
  - **After `add-aws-runtime-stack` apply**: `DomainName` SHALL be
    the ALB DNS name produced by the `aws-compute` capability, and
    `GET /api/*` requests SHALL be forwarded to the API service.
  - **After `add-aws-runtime-stack` destroy**: `DomainName` SHALL
    return to `placeholder.invalid` so the bootstrap distribution
    remains valid in isolation.

The behavior's path pattern, cache policy, origin-request policy, and
allowed methods SHALL be owned by the bootstrap root and SHALL
remain unchanged when the runtime-stack root mutates the origin.

#### Scenario: Default behavior serves the SPA bucket

- **WHEN** `GET https://<dist-id>.cloudfront.net/` is requested after
  the operator uploads an `index.html` to `nica-erp-web`
- **THEN** the response SHALL return that `index.html` with HTTP 200

#### Scenario: `/api/*` behavior is declared but non-functional pre-runtime

- **WHEN** `GET https://<dist-id>.cloudfront.net/api/healthz` is
  requested after bootstrap and before `add-aws-runtime-stack` runs
- **THEN** the response SHALL be an HTTP 5xx CloudFront origin error

#### Scenario: `/api/*` behavior reaches the ALB post-runtime

- **WHEN** `GET https://<dist-id>.cloudfront.net/api/healthz` is
  requested at least 5 minutes after `add-aws-runtime-stack` apply
  completes
- **THEN** the response SHALL be HTTP 200 with a JSON body containing
  `"db":"ok"`
