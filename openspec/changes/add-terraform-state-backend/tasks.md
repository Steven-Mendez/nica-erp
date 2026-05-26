## 1. Layout and provider scaffolding

- [x] 1.1 Create directory `infra/terraform/bootstrap/` and add
      `infra/terraform/.gitignore` blocking `.terraform/`,
      `*.tfstate`, `*.tfstate.*`, `terraform.tfvars`,
      `.deploy-image-tag`.
- [x] 1.2 Author `infra/terraform/bootstrap/versions.tf` pinning
      Terraform `>= 1.6` and `hashicorp/aws ~> 5.0`.
- [x] 1.3 Author `infra/terraform/bootstrap/providers.tf` declaring
      the `aws` provider with `region = var.aws_region` and
      `default_tags { tags = { Project = "nica-erp" } }`. No `backend`
      block — bootstrap uses local state.
- [x] 1.4 Author `infra/terraform/bootstrap/variables.tf` declaring
      `aws_region` (string, default `"us-east-1"`) and the
      `terraform.tfvars.example` documenting it.

## 2. Terraform state backend (S3 + DynamoDB)

- [x] 2.1 Author `infra/terraform/bootstrap/state.tf`: create
      `aws_s3_bucket.tf_state` named `nica-erp-tf-state` with
      `aws_s3_bucket_versioning` enabled,
      `aws_s3_bucket_server_side_encryption_configuration` set to
      `aws:kms` with `alias/aws/s3`, and
      `aws_s3_bucket_public_access_block` with all four flags `true`.
- [x] 2.2 Add a bucket policy on `nica-erp-tf-state` denying any
      request whose `aws:SecureTransport` is `false`.
- [x] 2.3 Create `aws_dynamodb_table.tf_lock` named `nica-erp-tf-lock`
      with `billing_mode = "PAY_PER_REQUEST"`, hash key `LockID`
      (string), explicit tag `Project=nica-erp`.
- [x] 2.4 Expose outputs `tf_state_bucket`,
      `tf_state_bucket_arn`, `tf_lock_table`,
      `tf_lock_table_arn`.

## 3. Image registry (ECR)

- [x] 3.1 Author `infra/terraform/bootstrap/ecr.tf`: create
      `aws_ecr_repository.api` named `nica-erp` with
      `image_tag_mutability = "IMMUTABLE"` and
      `image_scanning_configuration.scan_on_push = true`; explicit
      tag `Project=nica-erp`.
- [x] 3.2 Attach `aws_ecr_lifecycle_policy.api` with rule selecting
      `tagStatus=any`, `countType=imageCountMoreThan`,
      `countNumber=5`, action `expire`.
- [x] 3.3 Expose output `ecr_repository_url`.

## 4. SPA bucket and CloudFront distribution

- [x] 4.1 Author `infra/terraform/bootstrap/web.tf`: create
      `aws_s3_bucket.web` named `nica-erp-web` with
      `aws_s3_bucket_server_side_encryption_configuration` set to
      `AES256` and `aws_s3_bucket_public_access_block` with all four
      flags `true`; explicit tag `Project=nica-erp`.
- [x] 4.2 Create `aws_cloudfront_origin_access_control.web` with
      `signing_protocol="sigv4"`, `signing_behavior="always"`,
      `origin_access_control_origin_type="s3"`.
- [x] 4.3 Create `aws_cloudfront_distribution.web` with:
      - viewer cert: default `cloudfront_default_certificate=true`,
        `minimum_protocol_version="TLSv1.2_2021"`, no aliases;
      - `price_class="PriceClass_100"`;
      - origin `web-s3` → `nica-erp-web` regional domain via OAC;
      - origin `api-placeholder` → `placeholder.invalid` with
        `custom_origin_config { origin_protocol_policy="http-only", http_port=80, origin_ssl_protocols=["TLSv1.2"] }`;
      - default cache behavior: `target_origin_id="web-s3"`,
        allowed methods `["GET","HEAD","OPTIONS"]`, cached
        `["GET","HEAD"]`, `viewer_protocol_policy="redirect-to-https"`,
        AWS managed cache policy `CachingOptimized`
        (`658327ea-f89d-4fab-a63d-7e88639e58f6`);
      - ordered cache behavior `/api/*`: `target_origin_id="api-placeholder"`,
        allowed methods `["GET","HEAD","OPTIONS","PUT","POST","PATCH","DELETE"]`,
        cached `["GET","HEAD"]`,
        `viewer_protocol_policy="redirect-to-https"`,
        AWS managed cache policy `CachingDisabled`
        (`4135ea2d-6df8-44a3-9df3-4b5a84be39ad`), origin-request
        policy `AllViewerExceptHostHeader`
        (`b689b0a8-53d0-40ab-baf2-68738e2966ac`);
      - custom error responses: `403` and `404` both rewritten to
        `/index.html` with response code `200` and TTL `0`.
- [x] 4.4 Attach `aws_s3_bucket_policy.web` allowing
      `cloudfront.amazonaws.com` to `s3:GetObject` only when
      `AWS:SourceArn` equals the distribution ARN.
- [x] 4.5 Expose outputs `cloudfront_distribution_id`,
      `cloudfront_distribution_arn`,
      `cloudfront_distribution_domain`, `web_bucket`.

## 5. Bootstrap scripts and Makefile targets

- [x] 5.1 Author `scripts/bootstrap.sh` (bash, `set -euo pipefail`):
      check `aws sts get-caller-identity`, run
      `terraform -chdir=infra/terraform/bootstrap init`,
      then `terraform -chdir=infra/terraform/bootstrap apply -auto-approve`,
      then `terraform -chdir=infra/terraform/bootstrap output` and
      print the four named outputs. Exit non-zero on any failure.
- [x] 5.2 Author `scripts/destroy-bootstrap.sh` (bash,
      `set -euo pipefail`):
      (a) read a confirmation line from stdin and abort if it is not
      `nica-erp-bootstrap`; (b) call
      `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp`
      and abort if any returned ARN is outside the bootstrap allow-list
      (`nica-erp-tf-state`, `nica-erp-tf-lock`, `nica-erp` ECR,
      `nica-erp-web`, the bootstrap CloudFront distribution); (c)
      empty `nica-erp-tf-state` (all versions), `nica-erp-web`, and
      the ECR repo; (d) run
      `terraform -chdir=infra/terraform/bootstrap destroy -auto-approve`.
- [x] 5.3 Add `Makefile` targets `bootstrap` and `destroy-bootstrap`
      delegating to the two scripts. Document them in `make help`.
      Do NOT add `deploy`, `destroy`, `plan`, `logs`, `deploy-web`,
      or `wipe` here — those belong to
      `add-deploy-destroy-automation`.

## 6. Verification (operator-run against real AWS)

These steps require AWS credentials and will incur the few-cents/month
idle cost of the persistent stack. They are the acceptance checklist
for whoever runs the first complete `make bootstrap`. The change does
not get archived until §6 is fully ticked.

**Blocked by AWS Support**: the target account (`469351852594`) has the
new-account CloudFront verification gate active — `aws_cloudfront_distribution.web`
fails with `AccessDenied: Your account must be verified...`. Support
case `177976097100373` is open under "Account and billing → Account
Activation, Account Verification". Tasks 6.1 – 6.4 cannot pass until
that case is resolved.

Partial verification has already been performed against account
`469351852594` on 2026-05-25:

- Canary + 12 of 14 resources applied cleanly (state bucket, lock
  table, ECR + lifecycle, SPA bucket, OAC, encryption / public
  access blocks / versioning / state bucket policy).
- `terraform validate` and `terraform fmt -check` clean.
- `make destroy-bootstrap` with the correct token successfully
  removed all 12 resources; tagging API returned an empty list
  afterwards.
- `make destroy-bootstrap` with a wrong token aborted without
  issuing any destructive call.

The boxes below stay unchecked until a single `make bootstrap` against
a clean post-verification account succeeds end-to-end (14/14
resources) and all sub-tasks below pass on that same run.

- [ ] 6.1 Run `make bootstrap` against a clean AWS account; confirm
      stdout lists `cloudfront_distribution_domain`,
      `tf_state_bucket`, `ecr_repository_url`, `web_bucket`.
- [ ] 6.2 Upload a placeholder `index.html` with
      `aws s3 cp index.html "s3://$(terraform -chdir=infra/terraform/bootstrap output -raw web_bucket)/index.html"`,
      then curl `https://<dist>.cloudfront.net/` and confirm HTTP 200
      + the placeholder body.
- [ ] 6.3 Curl `https://<dist>.cloudfront.net/non-existent` and
      confirm HTTP 200 with the same `index.html` body (custom 404
      rewrite).
- [ ] 6.4 Curl `https://<dist>.cloudfront.net/api/healthz` and confirm
      an HTTP 5xx CloudFront origin error (placeholder origin behaves
      as declared).
- [ ] 6.5 Run `terraform -chdir=infra/terraform/bootstrap plan` a
      second time and confirm `No changes`.
- [ ] 6.6 Run `make destroy-bootstrap`, type the wrong string, confirm
      no AWS destructive call was issued and resources are intact.
      (Already verified on 2026-05-25; will be re-verified on the
      first complete bootstrap cycle.)
- [ ] 6.7 Run `make destroy-bootstrap`, type `nica-erp-bootstrap`,
      confirm buckets and ECR are emptied and the 14 Terraform
      resources are gone.
- [ ] 6.8 Run
      `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp`
      and confirm an empty result. (Already verified on 2026-05-25
      after the partial-bootstrap destroy; will be re-verified on the
      first complete cycle.)
