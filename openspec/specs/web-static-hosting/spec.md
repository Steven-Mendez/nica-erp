# web-static-hosting Specification

## Purpose
TBD - created by archiving change add-terraform-state-backend. Update Purpose after archive.
## Requirements
### Requirement: S3 SPA bucket `nica-erp-web-<account-id>` holds the built SPA privately

The bootstrap Terraform root SHALL create an S3 bucket named
`nica-erp-web-${data.aws_caller_identity.current.account_id}` with
server-side encryption set to `AES256` (SSE-S3), `BlockPublicAccess`
with all four flags (`BlockPublicAcls`, `BlockPublicPolicy`,
`IgnorePublicAcls`, `RestrictPublicBuckets`) set to `true`, and the
tag `Project=nica-erp`. The bucket policy SHALL grant `s3:GetObject`
only to the CloudFront service principal whose `AWS:SourceArn` matches
the distribution created by this change, and SHALL deny all other
principals. The bucket name is exposed as the `web_bucket` Terraform
output.

#### Scenario: SPA bucket is not publicly readable

- **WHEN** an unauthenticated HTTPS request hits the bucket regional
  domain for the SPA bucket (e.g.
  `https://${web_bucket}.s3.us-east-1.amazonaws.com/index.html`)
- **THEN** the response status SHALL be `403`

#### Scenario: CloudFront can read the SPA bucket via OAC

- **WHEN** an OAC-signed request reaches the bucket from the
  distribution created by this change
- **THEN** the response SHALL succeed (`200`) and serve the requested
  object

### Requirement: CloudFront distribution fronts the SPA over the default cert

The bootstrap Terraform root SHALL create one CloudFront distribution
attached to the SPA bucket via an Origin Access Control (OAC, signing
protocol `sigv4`, signing behavior `always`). The distribution SHALL
use the default `*.cloudfront.net` viewer certificate with TLSv1.2_2021
minimum protocol version (no ACM, no `Aliases`). Price class SHALL be
`PriceClass_100`. The distribution SHALL carry the tag
`Project=nica-erp`.

#### Scenario: Default cert and no aliases

- **WHEN** `aws cloudfront get-distribution --id <dist-id>` is called
  after bootstrap
- **THEN** `DistributionConfig.Aliases.Quantity` SHALL be `0` and
  `DistributionConfig.ViewerCertificate.CloudFrontDefaultCertificate`
  SHALL be `true`

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

### Requirement: SPA-friendly custom error responses

The distribution SHALL declare two custom error responses: status code
`403` SHALL be rewritten to `/index.html` with response code `200` and
a TTL of 0 seconds, and status code `404` SHALL be rewritten to
`/index.html` with response code `200` and a TTL of 0 seconds.

#### Scenario: Deep-link to non-S3 path returns the SPA shell

- **WHEN** `GET https://<dist-id>.cloudfront.net/anything-not-uploaded`
  is requested after the operator uploads an `index.html`
- **THEN** the response SHALL be HTTP 200 and the body SHALL be the
  contents of `index.html`

