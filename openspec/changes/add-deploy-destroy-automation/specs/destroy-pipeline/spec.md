## ADDED Requirements

### Requirement: `make destroy` tears down the ephemeral stack

The root `Makefile` SHALL declare a target `destroy` that delegates
to `scripts/destroy.sh`. The script SHALL:

1. `scripts/check-credentials.sh`.
2. `terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`.
3. Optionally (gated by `DESTROY_WEB_ASSETS=1`) empty the
   `nica-erp-web` bucket via
   `aws s3 rm s3://nica-erp-web/ --recursive`.
4. Print the result of `scripts/verify-destroyed.sh` to stdout but
   SHALL NOT fail solely on a verify mismatch (verification is a
   *report*, not a gate).

The script SHALL complete within 15 minutes on a healthy account.

#### Scenario: Destroy on an already-destroyed account is a no-op

- **WHEN** `make destroy` is run when the demo env is already
  destroyed
- **THEN** the script SHALL exit `0` within 60 seconds (Terraform
  reports no changes) and SHALL NOT touch the SPA bucket

#### Scenario: DESTROY_WEB_ASSETS empties the SPA bucket

- **WHEN** `DESTROY_WEB_ASSETS=1 make destroy` is run with the SPA
  bucket non-empty
- **THEN** after the script exits, `aws s3 ls s3://nica-erp-web/`
  SHALL return no objects

### Requirement: `verify-destroyed.sh` enforces a bootstrap-only allow-list

`scripts/verify-destroyed.sh` SHALL query the AWS Resource Groups
Tagging API for `Project=nica-erp` and SHALL exit non-zero with a
diagnostic naming every offending ARN if any returned resource is
not in the allow-list. The allow-list SHALL contain exactly the
ARNs of:

- S3 bucket `nica-erp-tf-state`.
- DynamoDB table `nica-erp-tf-lock`.
- ECR repository `nica-erp`.
- S3 bucket `nica-erp-web`.
- The CloudFront distribution created by
  `add-terraform-state-backend` (resolved via Terraform output
  rather than hard-coded ARN).

Adding a new persistent resource SHALL require updating this
script in the same PR.

#### Scenario: A leftover RDS instance fails verification

- **WHEN** `verify-destroyed.sh` is run while an RDS instance
  tagged `Project=nica-erp` still exists outside the allow-list
- **THEN** the script SHALL exit non-zero with stdout listing the
  RDS ARN

#### Scenario: Bootstrap-only state passes verification

- **WHEN** `verify-destroyed.sh` is run immediately after
  `make destroy` with the bootstrap stack intact
- **THEN** the script SHALL exit `0` and stdout SHALL confirm
  "only bootstrap resources present"

### Requirement: `confirm-destroy.sh` is the shared confirmation helper

`scripts/confirm-destroy.sh` SHALL accept a single argument
(the literal expected confirmation string), prompt the operator
via `read -r`, and exit non-zero if the input does not match
exactly. Both `destroy.sh` (if guarded) and
`destroy-bootstrap.sh` (from
`add-terraform-state-backend`) SHALL source this helper rather
than re-implement the prompt.

#### Scenario: Wrong confirmation aborts

- **WHEN** the helper is invoked with `nica-erp-destroy` as the
  expected string and the operator types anything else
- **THEN** the helper SHALL exit non-zero and SHALL produce a
  one-line "mismatch" diagnostic

### Requirement: `make wipe` chains destroy + destroy-bootstrap at the Make layer

The root `Makefile` SHALL declare a target `wipe` whose body is
the literal sequence `$(MAKE) destroy` followed by
`$(MAKE) destroy-bootstrap`. There SHALL NOT be a `scripts/wipe.sh`;
wiping is a Makefile-level chain so each sub-target's own
confirmation prompt is preserved.

#### Scenario: wipe invokes both sub-targets

- **WHEN** `make wipe` is run
- **THEN** the operator SHALL be prompted by
  `destroy-bootstrap`'s confirmation step (`nica-erp-bootstrap`)
  after `destroy` completes
