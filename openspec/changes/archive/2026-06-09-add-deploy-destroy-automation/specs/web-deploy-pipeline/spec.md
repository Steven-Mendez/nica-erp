## ADDED Requirements

### Requirement: `make deploy-web` builds and uploads the SPA with CloudFront invalidation

The root `Makefile` SHALL declare a target `deploy-web` delegating
to `scripts/deploy-web.sh`. The script SHALL:

1. Read `cloudfront_distribution_id` and `web_bucket` from
   `terraform -chdir=infra/terraform/bootstrap output`.
2. Run `pnpm --filter @nica-erp/web build` (Vite reads
   `apps/web/.env.production`, so no inline env override is
   required).
3. Run `aws s3 sync apps/web/dist/ s3://<web_bucket>/ --delete --cache-control "public, max-age=31536000, immutable" --exclude index.html`.
4. Run `aws s3 cp apps/web/dist/index.html s3://<web_bucket>/index.html --cache-control "public, max-age=0, must-revalidate"`.
5. Run `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`
   and `aws cloudfront wait invalidation-completed --distribution-id <id> --id <invalidation-id>`.

The script SHALL exit non-zero on any step failure.

#### Scenario: Successful web deploy invalidates CloudFront

- **WHEN** `make deploy-web` is run with a clean SPA build
- **THEN** the script SHALL exit `0` and CloudWatch SHALL record
  exactly one CloudFront invalidation API call with paths `/*`

#### Scenario: Index has zero TTL while assets are immutable

- **WHEN** the SPA is freshly uploaded
- **THEN** `aws s3api head-object --bucket <web_bucket> --key index.html`
  SHALL return `CacheControl: public, max-age=0, must-revalidate`
- **AND** `aws s3api head-object --bucket <web_bucket> --key assets/<any-hashed-file>`
  SHALL return `CacheControl: public, max-age=31536000, immutable`

### Requirement: `apps/web/.env.production` sets `VITE_API_BASE_URL=/api`

The repository SHALL commit `apps/web/.env.production` containing
exactly the line `VITE_API_BASE_URL=/api` (with optional trailing
newline). This file SHALL be tracked by git so every operator's
production build resolves the API base URL the same way.

#### Scenario: Production builds embed the relative API URL

- **WHEN** `pnpm --filter @nica-erp/web build` runs and the
  resulting `dist/assets/*.js` is inspected
- **THEN** the bundle SHALL contain the literal string `/api/healthz`
  (or another `/api/` path used by the SPA) and SHALL NOT contain
  any `http://localhost:8000` reference

### Requirement: SPA reads `VITE_API_BASE_URL` for its API base path

The SPA SHALL resolve its API base URL via
`import.meta.env.VITE_API_BASE_URL` in the module that issues the
healthz fetch (and any other API call). The module SHALL fall back
to a sensible default for local development (e.g.
`http://localhost:8000`) when the env var is unset, mirroring
`apps/web/.env.local.example`.

#### Scenario: Local dev hits the API on :8000

- **WHEN** `pnpm --filter @nica-erp/web dev` runs with
  `VITE_API_BASE_URL` unset
- **THEN** the healthz card SHALL issue a request to
  `http://localhost:8000/api/healthz`

#### Scenario: Production build hits CloudFront same-origin

- **WHEN** the production-built SPA is loaded from
  `https://<dist-id>.cloudfront.net/`
- **THEN** the healthz card SHALL issue a request to
  `https://<dist-id>.cloudfront.net/api/healthz`
