#!/usr/bin/env bash
# scripts/bootstrap.sh — provision the persistent half of nica-erp on AWS.
#
# Creates: nica-erp-tf-state-<account-id> (S3), nica-erp-tf-lock (DynamoDB),
# nica-erp (ECR), nica-erp-web-<account-id> (S3), and the SPA CloudFront
# distribution. Idempotent: re-running against an already-bootstrapped
# account is a no-op.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/bootstrap"

# The project mandates the `nica-erp` AWS CLI profile and the us-east-1
# region; the default profile and any other region must not be used.
# Override is intentionally not allowed.
export AWS_PROFILE="nica-erp"
export AWS_REGION="us-east-1"
export AWS_DEFAULT_REGION="us-east-1"

if ! command -v terraform >/dev/null 2>&1; then
  echo "ERROR: terraform not found on PATH. Install Terraform >= 1.6." >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found on PATH. Install AWS CLI v2." >&2
  exit 1
fi

echo "==> Verifying AWS credentials (profile: ${AWS_PROFILE}, region: ${AWS_REGION})"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "ERROR: 'aws sts get-caller-identity' failed for profile '${AWS_PROFILE}'." >&2
  echo "Configure it with: aws configure --profile ${AWS_PROFILE}" >&2
  exit 1
fi

# Canary calls: each touches a different service with a cheap read so a
# missing IAM permission surfaces here instead of mid-apply, when half
# the persistent set has already been created.
check_perm() {
  local label="$1"
  shift
  if ! "$@" >/dev/null 2>&1; then
    echo "  FAIL  ${label}" >&2
    return 1
  fi
  echo "  OK    ${label}"
}

echo "==> IAM permissions canary"
canary_ok=1
check_perm "s3:ListAllMyBuckets"          aws s3api list-buckets                              || canary_ok=0
check_perm "dynamodb:ListTables"          aws dynamodb list-tables --max-items 1              || canary_ok=0
check_perm "ecr:DescribeRepositories"     aws ecr describe-repositories --max-results 1       || canary_ok=0
check_perm "cloudfront:ListDistributions" aws cloudfront list-distributions --max-items 1     || canary_ok=0

if [[ ${canary_ok} -ne 1 ]]; then
  cat >&2 <<'MSG'

ERROR: the nica-erp profile is missing IAM permissions required by the
bootstrap. Attach a policy with at minimum:

  - s3        : CreateBucket, PutBucket*, GetBucket*, DeleteBucket*,
                PutObject, GetObject, DeleteObject*, ListBucket,
                ListAllMyBuckets, PutBucketVersioning, PutBucketPolicy,
                PutBucketPublicAccessBlock, PutBucketEncryption
  - dynamodb  : CreateTable, DescribeTable, ListTables, DeleteTable,
                TagResource, UntagResource, ListTagsOfResource
  - ecr       : CreateRepository, DescribeRepositories,
                DeleteRepository, PutLifecyclePolicy, GetLifecyclePolicy,
                BatchDeleteImage, ListImages, TagResource
  - cloudfront: CreateDistribution, GetDistribution, UpdateDistribution,
                DeleteDistribution, CreateOriginAccessControl,
                GetOriginAccessControl, DeleteOriginAccessControl,
                ListDistributions, TagResource
  - tag       : tag:GetResources (for destroy-bootstrap's allow-list check)
  - iam       : CreateServiceLinkedRole (first CloudFront use per account)
MSG
  exit 1
fi

echo "==> terraform init"
terraform -chdir="${TF_DIR}" init -input=false

echo "==> terraform apply"
terraform -chdir="${TF_DIR}" apply -auto-approve -input=false

echo
echo "==> Bootstrap outputs"
for key in cloudfront_distribution_domain tf_state_bucket ecr_repository_url web_bucket; do
  value="$(terraform -chdir="${TF_DIR}" output -raw "${key}")"
  printf '%s = %s\n' "${key}" "${value}"
done
