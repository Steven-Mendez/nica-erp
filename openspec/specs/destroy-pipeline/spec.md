# destroy-pipeline Specification

## Purpose
TBD - created by archiving change add-deploy-destroy-automation. Update Purpose after archive.

## Requirements
### Requirement: `make destroy` dispatches the destroy workflow on GitHub Actions

The root `Makefile` SHALL declare a target `destroy` that invokes
`gh workflow run destroy.yml --ref main -f confirm=nica-erp-ephemeral`.
The target SHALL exit non-zero with a clear diagnostic if `gh` is
missing or unauthenticated and SHALL NOT invoke `terraform` or any
destroy script locally. The destroy itself runs on the GHA runner
under the `nica-erp-ci-destroy` OIDC-assumed role.

#### Scenario: `make destroy` triggers the remote workflow with the confirmation pre-filled

- **WHEN** `make destroy` is run on a host with `gh` authenticated
- **THEN** the command SHALL invoke
  `gh workflow run destroy.yml --ref main -f confirm=nica-erp-ephemeral`
  and SHALL NOT call `terraform destroy` locally

### Requirement: destroy.yml requires a literal confirmation input

`.github/workflows/destroy.yml` SHALL declare a required input
`confirm` of `type: string` with no default. The workflow's first
step SHALL assert `inputs.confirm == 'nica-erp-ephemeral'` and
SHALL exit the workflow non-zero before any AWS API call on
mismatch.

#### Scenario: Wrong confirmation aborts before any AWS call

- **WHEN** `destroy.yml` is dispatched with `confirm=anything-else`
- **THEN** the workflow SHALL exit non-zero in its first step and
  SHALL NOT invoke `terraform destroy` or any `aws ecs`/`aws s3`
  call

#### Scenario: Correct confirmation proceeds

- **WHEN** `destroy.yml` is dispatched with
  `confirm=nica-erp-ephemeral`
- **THEN** the workflow SHALL proceed past the first step and
  invoke `terraform destroy` against the ephemeral root

### Requirement: destroy.yml tears down the ephemeral stack

After the confirmation step, `destroy.yml` SHALL execute, in
order, on a single `ubuntu-latest` job:

1. `actions/checkout@v6`.
2. `aws-actions/configure-aws-credentials@v4` assuming
   `${{ vars.AWS_DESTROY_ROLE_ARN }}` via OIDC.
3. `terraform -chdir=infra/terraform/envs/demo init -input=false`.
4. `terraform -chdir=infra/terraform/envs/demo destroy -auto-approve`.
5. Optionally (gated by the workflow input `clean_web_assets`,
   default `false`) empty the `nica-erp-web` bucket via
   `aws s3 rm s3://nica-erp-web-<account-id>/ --recursive`.
6. Run `scripts/verify-destroyed.sh` and append its result to
   `$GITHUB_STEP_SUMMARY` (verification is a *report*, not a
   gate).

The workflow SHALL complete within 15 minutes on a healthy
account.

#### Scenario: Destroy on an already-destroyed account is a no-op

- **WHEN** `destroy.yml` is dispatched against an account whose
  demo env is already destroyed
- **THEN** the workflow SHALL exit `0` within 60 seconds (Terraform
  reports no changes) and SHALL NOT touch the SPA bucket

#### Scenario: clean_web_assets empties the SPA bucket

- **WHEN** `destroy.yml` is dispatched with `clean_web_assets=true`
  and the SPA bucket non-empty
- **THEN** after the workflow exits,
  `aws s3 ls s3://nica-erp-web-<account-id>/` SHALL return no
  objects

### Requirement: destroy.yml authenticates via OIDC, not static keys

`destroy.yml` SHALL declare top-level
`permissions: { id-token: write, contents: read }` and SHALL use
`aws-actions/configure-aws-credentials@v4` with `role-to-assume`
pointing at the GitHub repository variable `AWS_DESTROY_ROLE_ARN`.
It SHALL NOT reference `AWS_ACCESS_KEY_ID` or
`AWS_SECRET_ACCESS_KEY` repository secrets.

#### Scenario: No long-lived AWS keys in destroy.yml

- **WHEN** `.github/workflows/destroy.yml` is inspected
- **THEN** it SHALL contain no reference to `AWS_ACCESS_KEY_ID` or
  `AWS_SECRET_ACCESS_KEY`
- **AND** it SHALL contain `permissions: id-token: write` and an
  `aws-actions/configure-aws-credentials` invocation referencing
  `vars.AWS_DESTROY_ROLE_ARN`

### Requirement: destroy.yml serializes concurrent dispatches

`destroy.yml` SHALL declare a `concurrency` block with
`group: destroy` and `cancel-in-progress: false`. Two simultaneous
dispatches SHALL queue rather than race.

#### Scenario: Two dispatches queue cleanly

- **WHEN** `destroy.yml` is dispatched twice in quick succession
- **THEN** the second run SHALL wait for the first to complete
  uninterrupted

### Requirement: `verify-destroyed.sh` enforces a bootstrap-only allow-list

`scripts/verify-destroyed.sh` SHALL query the AWS Resource Groups
Tagging API for `Project=nica-erp` and SHALL exit non-zero with a
diagnostic naming every offending ARN if any returned resource is
not in the allow-list. The allow-list SHALL contain exactly the
ARNs of:

- S3 bucket `nica-erp-tf-state-<account-id>`.
- DynamoDB table `nica-erp-tf-lock`.
- ECR repository `nica-erp`.
- S3 bucket `nica-erp-web-<account-id>`.
- The CloudFront distribution created by the bootstrap.
- The GitHub OIDC provider and the two CI IAM roles
  (`nica-erp-ci-deploy`, `nica-erp-ci-destroy`).

Adding a new persistent resource SHALL require updating this
script in the same PR.

#### Scenario: A leftover RDS instance fails verification

- **WHEN** `verify-destroyed.sh` is run while an RDS instance
  tagged `Project=nica-erp` still exists outside the allow-list
- **THEN** the script SHALL exit non-zero with stdout listing the
  RDS ARN

#### Scenario: Bootstrap-only state passes verification

- **WHEN** `verify-destroyed.sh` is run immediately after
  `destroy.yml` completes with the bootstrap stack intact
- **THEN** the script SHALL exit `0` and stdout SHALL confirm
  "only bootstrap resources present"

### Requirement: `confirm-destroy.sh` is the shared confirmation helper for operator-host-side destroys

`scripts/confirm-destroy.sh` SHALL accept a single argument
(the literal expected confirmation string), prompt the operator
via `read -r`, and exit non-zero if the input does not match
exactly. `scripts/destroy-bootstrap.sh` (from
`add-terraform-state-backend`) SHALL source this helper rather
than re-implement the prompt. The `make destroy` path does not
use this helper because its confirmation lives in the workflow
input instead.

#### Scenario: Wrong confirmation aborts

- **WHEN** the helper is invoked with `nica-erp-bootstrap` as the
  expected string and the operator types anything else
- **THEN** the helper SHALL exit non-zero and SHALL produce a
  one-line "mismatch" diagnostic

### Requirement: `make wipe` chains destroy + destroy-bootstrap at the Make layer

The root `Makefile` SHALL declare a target `wipe` whose body is
the literal sequence `$(MAKE) destroy` (which dispatches the
remote workflow) followed by `$(MAKE) destroy-bootstrap` (which
runs the operator-host-side script with its terminal-prompt
confirmation). There SHALL NOT be a `scripts/wipe.sh`; wiping is
a Makefile-level chain so each sub-target keeps its own
confirmation contract.

#### Scenario: wipe invokes both sub-targets

- **WHEN** `make wipe` is run on an account with both stacks alive
- **THEN** the `destroy.yml` workflow SHALL dispatch first; on
  its completion, the operator SHALL be prompted by
  `destroy-bootstrap.sh`'s terminal confirmation
  (`Type 'nica-erp-bootstrap' to confirm`)
