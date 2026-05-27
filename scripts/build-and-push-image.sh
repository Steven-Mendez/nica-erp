#!/usr/bin/env bash
# scripts/build-and-push-image.sh — build the nica-erp API image and push it to ECR.
#
# Per ADR-0030, image builds run inside the GitHub Actions deploy workflow.
# This script also runs on the operator host as the escape-hatch path
# (`make build-image`). The script is intentionally chatty so a future
# operator can see exactly which commit produced which tag.
#
# Inputs:
#   AWS_PROFILE / AWS_REGION : operator-host path pins nica-erp / us-east-1.
#                              CI path (OIDC) ships AWS_ACCESS_KEY_ID in the
#                              environment; the script then skips the profile
#                              pin so the workflow-issued credentials win.
#   ALLOW_DIRTY              : opt-out. When set to 1, a non-clean working tree
#                              still builds but the tag is suffixed with
#                              "-dirty-<unix-ts>" and a warning is emitted.
#
# Outputs:
#   - One immutable image in the bootstrap ECR repository tagged <short-sha>
#     (or <short-sha>-dirty-<unix-ts>).
#   - .deploy-image-tag at repo root containing that tag (gitignored).
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/bootstrap"
API_DIR="${ROOT_DIR}/apps/api"

# Operator-host path: pin the `nica-erp` profile and us-east-1.
# CI path (OIDC): AWS_ACCESS_KEY_ID is already exported by
# aws-actions/configure-aws-credentials; leaving AWS_PROFILE unset lets the
# workflow-issued credentials win.
if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

# ----------------------------------------------------------------------------
# Prerequisites
# ----------------------------------------------------------------------------

for tool in aws docker git terraform; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "ERROR: required tool '${tool}' not found on PATH." >&2
    exit 1
  fi
done

if ! git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: ${ROOT_DIR} is not inside a git repository." >&2
  exit 1
fi

echo "==> Verifying AWS credentials (profile: ${AWS_PROFILE:-<env>}, region: ${AWS_REGION})"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    echo "ERROR: 'aws sts get-caller-identity' failed with the env-supplied credentials." >&2
  else
    echo "ERROR: 'aws sts get-caller-identity' failed for profile '${AWS_PROFILE}'." >&2
    echo "Configure it with: aws configure --profile ${AWS_PROFILE}" >&2
  fi
  exit 1
fi

echo "==> Verifying Docker daemon is reachable"
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: 'docker info' failed. Is Docker Desktop running?" >&2
  exit 1
fi

echo "==> Resolving ECR repository URL from terraform output"
if ! ECR_REPO_URL="$(terraform -chdir="${TF_DIR}" output -raw ecr_repository_url 2>/dev/null)"; then
  echo "ERROR: terraform output 'ecr_repository_url' not available in ${TF_DIR}." >&2
  echo "Run 'make bootstrap' first." >&2
  exit 1
fi
if [[ -z "${ECR_REPO_URL}" ]]; then
  echo "ERROR: terraform output 'ecr_repository_url' is empty." >&2
  exit 1
fi
echo "    ECR repo: ${ECR_REPO_URL}"

# ----------------------------------------------------------------------------
# Tag derivation + dirty-tree handling
# ----------------------------------------------------------------------------

GIT_SHA="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
SHORT_SHA="$(git -C "${ROOT_DIR}" rev-parse --short HEAD)"

dirty=0
if ! git -C "${ROOT_DIR}" diff --quiet; then dirty=1; fi
if ! git -C "${ROOT_DIR}" diff --cached --quiet; then dirty=1; fi

if [[ ${dirty} -eq 1 ]]; then
  if [[ "${ALLOW_DIRTY:-0}" != "1" ]]; then
    echo "ERROR: working tree has uncommitted changes:" >&2
    git -C "${ROOT_DIR}" status --short >&2
    echo >&2
    echo "Refusing to build a non-reproducible image." >&2
    echo "Commit the changes, or re-run with ALLOW_DIRTY=1 to push a -dirty tag." >&2
    exit 1
  fi
  TAG="${SHORT_SHA}-dirty-$(date +%s)"
  echo "WARNING: ALLOW_DIRTY=1 — building from a dirty working tree." >&2
  echo "WARNING: pushed tag will be '${TAG}' (immutable, not reproducible)." >&2
else
  TAG="${SHORT_SHA}"
fi

IMAGE_REF="${ECR_REPO_URL}:${TAG}"
echo "==> Target image: ${IMAGE_REF}"
echo "    GIT_SHA      = ${GIT_SHA}"

# ----------------------------------------------------------------------------
# ECR login
# ----------------------------------------------------------------------------

# Strip everything after the first slash so we log in to the registry, not
# the repository path.
REGISTRY="${ECR_REPO_URL%%/*}"

echo "==> Logging Docker in to ${REGISTRY}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

# ----------------------------------------------------------------------------
# Build + push
# ----------------------------------------------------------------------------

echo "==> Building image (platform=linux/amd64)"
docker build \
  --platform linux/amd64 \
  --build-arg "GIT_SHA=${GIT_SHA}" \
  -t "nica-erp:${TAG}" \
  -t "${IMAGE_REF}" \
  "${API_DIR}"

echo "==> Pushing ${IMAGE_REF}"
docker push "${IMAGE_REF}"

# ----------------------------------------------------------------------------
# Hand-off artifact
# ----------------------------------------------------------------------------

DEPLOY_TAG_FILE="${ROOT_DIR}/.deploy-image-tag"
printf '%s\n' "${TAG}" > "${DEPLOY_TAG_FILE}"
echo "==> Wrote ${DEPLOY_TAG_FILE} (tag=${TAG})"
echo "    Deploy automation reads this file; see add-deploy-destroy-automation."
