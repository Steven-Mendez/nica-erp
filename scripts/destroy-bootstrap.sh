#!/usr/bin/env bash
# scripts/destroy-bootstrap.sh — tear down the persistent half of nica-erp.
#
# Refuses to run while any ephemeral Project=nica-erp resource is alive
# (those belong to add-aws-runtime-stack and must be destroyed first).
# Requires the operator to type the literal string `nica-erp-bootstrap`
# on stdin before any destructive action is taken.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/bootstrap"

# Pinned profile and region; see scripts/bootstrap.sh for rationale.
export AWS_PROFILE="nica-erp"
export AWS_REGION="us-east-1"
export AWS_DEFAULT_REGION="us-east-1"

CONFIRM_TOKEN="nica-erp-bootstrap"

ECR_REPO="nica-erp"
LOCK_TABLE="nica-erp-tf-lock"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: $1 not found on PATH." >&2
    exit 1
  fi
}

require_cmd terraform
require_cmd aws

echo "==> Verifying AWS credentials (profile: ${AWS_PROFILE}, region: ${AWS_REGION})"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "ERROR: 'aws sts get-caller-identity' failed for profile '${AWS_PROFILE}'." >&2
  echo "Configure it with: aws configure --profile ${AWS_PROFILE}" >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
STATE_BUCKET="nica-erp-tf-state-${ACCOUNT_ID}"
WEB_BUCKET="nica-erp-web-${ACCOUNT_ID}"

"${ROOT_DIR}/scripts/confirm-destroy.sh" "${CONFIRM_TOKEN}"

echo "==> Checking for ephemeral nica-erp resources"
# Bootstrap allow-list: any ARN that contains one of these substrings is part
# of the persistent set this script owns. Anything else means add-aws-runtime-stack
# is still alive and must be torn down first.
allow_grep="(:s3:::nica-erp-tf-state-${ACCOUNT_ID}\$|:s3:::nica-erp-web-${ACCOUNT_ID}\$|:dynamodb:[^:]+:[0-9]+:table/nica-erp-tf-lock\$|:ecr:[^:]+:[0-9]+:repository/nica-erp\$|:cloudfront::[0-9]+:distribution/)"

tagged_arns="$(
  aws resourcegroupstaggingapi get-resources \
    --tag-filters "Key=Project,Values=nica-erp" \
    --query 'ResourceTagMappingList[].ResourceARN' \
    --output text \
    | tr '\t' '\n' \
    | sed '/^$/d'
)"

offenders=""
while IFS= read -r arn; do
  [ -z "${arn}" ] && continue
  if ! [[ "${arn}" =~ ${allow_grep} ]]; then
    offenders="${offenders}${arn}"$'\n'
  fi
done <<<"${tagged_arns}"

if [[ -n "${offenders}" ]]; then
  echo "ERROR: ephemeral Project=nica-erp resources still exist; refusing to destroy bootstrap." >&2
  echo "Run 'make destroy' (from add-deploy-destroy-automation) first. Offenders:" >&2
  while IFS= read -r offender; do
    [[ -z "${offender}" ]] && continue
    echo "  - ${offender}" >&2
  done <<<"${offenders}"
  exit 1
fi

delete_batch() {
  # $1 = bucket, $2 = JMESPath selecting Versions[] or DeleteMarkers[]
  local bucket="$1"
  local selector="$2"
  local payload

  while :; do
    payload="$(
      aws s3api list-object-versions \
        --bucket "${bucket}" \
        --max-items 1000 \
        --output json \
        --query "{Objects: ${selector}[].{Key:Key,VersionId:VersionId}}"
    )"
    # No more items → payload is `{"Objects": null}`. Exit the loop.
    if [[ -z "${payload}" ]] || [[ "${payload}" == "null" ]] \
       || echo "${payload}" | grep -q '"Objects": null'; then
      break
    fi
    aws s3api delete-objects \
      --bucket "${bucket}" \
      --delete "${payload}" >/dev/null
  done
}

empty_versioned_bucket() {
  local bucket="$1"

  if ! aws s3api head-bucket --bucket "${bucket}" 2>/dev/null; then
    echo "    (bucket ${bucket} does not exist; skipping)"
    return 0
  fi

  echo "    deleting object versions in ${bucket}"
  delete_batch "${bucket}" "Versions"

  echo "    deleting delete-markers in ${bucket}"
  delete_batch "${bucket}" "DeleteMarkers"
}

echo "==> Emptying ${STATE_BUCKET}"
empty_versioned_bucket "${STATE_BUCKET}"

echo "==> Emptying ${WEB_BUCKET}"
empty_versioned_bucket "${WEB_BUCKET}"

echo "==> Deleting all images in ECR repository ${ECR_REPO}"
if aws ecr describe-repositories --repository-names "${ECR_REPO}" >/dev/null 2>&1; then
  image_ids="$(
    aws ecr list-images \
      --repository-name "${ECR_REPO}" \
      --query 'imageIds' \
      --output json
  )"
  if [[ "${image_ids}" != "[]" ]] && [[ -n "${image_ids}" ]]; then
    aws ecr batch-delete-image \
      --repository-name "${ECR_REPO}" \
      --image-ids "${image_ids}" >/dev/null
  fi
else
  echo "    (repository ${ECR_REPO} does not exist; skipping)"
fi

echo "==> terraform destroy"
terraform -chdir="${TF_DIR}" destroy -auto-approve -input=false

echo
echo "Bootstrap teardown complete. Lock table ${LOCK_TABLE} and the rest of the persistent set are gone."
