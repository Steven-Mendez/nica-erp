## ADDED Requirements

### Requirement: S3 bucket `nica-erp-web` holds the built SPA privately

The bootstrap Terraform root SHALL create an S3 bucket named
`nica-erp-web` with server-side encryption set to `AES256` (SSE-S3),
`BlockPublicAccess` with all four flags (`BlockPublicAcls`,
`BlockPublicPolicy`, `IgnorePublicAcls`, `RestrictPublicBuckets`) set
to `true`, and the tag `Project=nica-erp`. The bucket policy SHALL
grant `s3:GetObject` only to the CloudFront service principal whose
`AWS:SourceArn` matches the distribution created by this change, and
SHALL deny all other principals.

#### Scenario: SPA bucket is not publicly readable

- **WHEN** an unauthenticated HTTPS request hits
  `https://nica-erp-web.s3.us-east-1.amazonaws.com/index.html`
- **THEN** the response status SHALL be `403`

#### Scenario: CloudFront can read the SPA bucket via OAC

- **WHEN** an OAC-signed request reaches the bucket from the
  distribution created by this change
- **THEN** the response SHALL succeed (`200`) and serve the requested
  object

### Requirement: CloudFront distribution fronts the SPA over the default cert

The bootstrap Terraform root SHALL create one CloudFront distribution
attached to `nica-erp-web` via an Origin Access Control (OAC, signing
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
  `DomainName` is `placeholder.invalid` and whose
  `OriginProtocolPolicy` is `http-only`. This origin is a deliberate
  placeholder; the `add-aws-runtime-stack` change SHALL swap
  `DomainName` to the ALB DNS name without recreating the
  distribution.

#### Scenario: Default behavior serves the SPA bucket

- **WHEN** `GET https://<dist-id>.cloudfront.net/` is requested after
  the operator uploads an `index.html` to `nica-erp-web`
- **THEN** the response SHALL return that `index.html` with HTTP 200

#### Scenario: `/api/*` behavior is declared but non-functional

- **WHEN** `GET https://<dist-id>.cloudfront.net/api/healthz` is
  requested after bootstrap and before `add-aws-runtime-stack` runs
- **THEN** the response SHALL be an HTTP 5xx CloudFront origin error
  (the placeholder origin does not resolve)

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
