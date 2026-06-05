# image-publish-pipeline Specification

## Purpose
TBD - created by archiving change add-api-container-image. Update Purpose after archive.
## Requirements
### Requirement: `make build-image` builds and pushes the API image to ECR

The root `Makefile` SHALL declare a target `build-image` that
delegates to `scripts/build-and-push-image.sh`. The script SHALL
resolve the ECR repository URL via
`terraform -chdir=infra/terraform/bootstrap output -raw ecr_repository_url`,
authenticate Docker against ECR with
`aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <repo>`,
build the image with
`docker build --platform linux/amd64 --build-arg GIT_SHA=<full-sha> -t nica-erp:<short-sha> apps/api/`,
tag it as `${ecr_repository_url}:<short-sha>`, and push it.

#### Scenario: A clean build pushes one image

- **WHEN** `make build-image` is run from a clean working tree
- **THEN** `aws ecr describe-images --repository-name nica-erp --image-ids imageTag=<short-sha>`
  SHALL return exactly one image

### Requirement: Image tags derive from the current commit SHA

The build script SHALL compute `GIT_SHA=$(git rev-parse HEAD)` and
`SHORT_SHA=$(git rev-parse --short HEAD)`. The pushed tag SHALL be
`<short-sha>`. The `GIT_SHA` build arg SHALL receive the full
40-character SHA.

#### Scenario: Tag matches `git rev-parse --short HEAD`

- **WHEN** `make build-image` succeeds on commit `<full-sha>`
- **THEN** the ECR image's tag SHALL equal `git rev-parse --short <full-sha>`
- **AND** the image's environment SHALL have `GIT_SHA=<full-sha>`

### Requirement: Build refuses to run on a dirty working tree by default

The build script SHALL exit non-zero with a diagnostic message
naming the dirty files when `git diff --quiet` or
`git diff --cached --quiet` returns non-zero, UNLESS the environment
variable `ALLOW_DIRTY` is set to `1`. When `ALLOW_DIRTY=1`, the
script SHALL substitute the tag with `<short-sha>-dirty-<unix-ts>`
and SHALL print a warning to stderr before proceeding.

#### Scenario: Uncommitted change aborts the build

- **WHEN** `make build-image` is run with an unstaged modification
  to `apps/api/src/bootstrap/api.py` and `ALLOW_DIRTY` unset
- **THEN** the script SHALL exit non-zero and SHALL NOT issue a
  `docker push`

#### Scenario: ALLOW_DIRTY substitutes a dirty tag

- **WHEN** `ALLOW_DIRTY=1 make build-image` is run with uncommitted
  changes at unix timestamp `1734000000`
- **THEN** the pushed tag SHALL match
  `^[0-9a-f]{7,}-dirty-1734000000$` and the script SHALL print a
  warning to stderr containing the literal `dirty`

### Requirement: `.deploy-image-tag` records the last successfully pushed tag

On a successful push, the build script SHALL write the pushed tag
(without the repository URL) to `.deploy-image-tag` at repo root,
overwriting any prior content. The file SHALL be gitignored.

#### Scenario: Deploy automation can read the last built tag

- **WHEN** `make build-image` finishes with tag `abc1234`
- **THEN** `cat .deploy-image-tag` SHALL output exactly `abc1234`
  followed by a single newline

### Requirement: Build script fails fast on missing prerequisites

The script SHALL verify, before any docker command, that:
`aws sts get-caller-identity` succeeds (operator is authenticated),
`docker info` succeeds (daemon is reachable), the bootstrap
Terraform output `ecr_repository_url` is non-empty, and the working
directory is inside a git repository. Any failure SHALL produce a
diagnostic and exit non-zero before pulling or pushing anything.

#### Scenario: Missing AWS credentials abort early

- **WHEN** `make build-image` is run with `AWS_PROFILE` unset and
  no other AWS credential source
- **THEN** the script SHALL exit non-zero with a message naming
  `aws sts get-caller-identity` and SHALL NOT invoke `docker build`

