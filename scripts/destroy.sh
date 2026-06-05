#!/usr/bin/env bash
# scripts/destroy.sh — tear down the ephemeral demo stack.
#
# Called from .github/workflows/destroy.yml AND from `make destroy-local`.
# Same script on both surfaces. Bootstrap (state bucket, ECR, CloudFront,
# OIDC, IAM roles) survives — destroy-bootstrap.sh is the project-close
# operation that removes those.
#
# Env toggles:
#   DESTROY_WEB_ASSETS=1  — also `aws s3 rm` the SPA bucket. Defaults
#                           off so the SPA-bucket contents survive a
#                           destroy/redeploy cycle and the next deploy
#                           can serve the previous index.html while
#                           Terraform brings the stack up.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TF_DIR="${ROOT_DIR}/infra/terraform/envs/demo"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

echo "==> check-credentials"
"${ROOT_DIR}/scripts/check-credentials.sh"

account_id="$(aws sts get-caller-identity --query Account --output text)"
state_bucket="nica-erp-tf-state-${account_id}"

echo "==> terraform init (env: demo)"
terraform -chdir="${ENV_TF_DIR}" init -input=false -reconfigure \
  -backend-config="bucket=${state_bucket}"

echo "==> terraform destroy (env: demo)"
# image_tag is a required variable (no default) but is irrelevant for
# destroy — pass a placeholder so terraform stops complaining about the
# missing root input.
terraform -chdir="${ENV_TF_DIR}" destroy -auto-approve -input=false \
  -var "image_tag=destroy"

if [[ "${DESTROY_WEB_ASSETS:-0}" == "1" ]]; then
  web_bucket="nica-erp-web-${account_id}"
  echo "==> Emptying SPA bucket (DESTROY_WEB_ASSETS=1)"
  aws s3 rm "s3://${web_bucket}/" --recursive
fi

echo "==> verify-destroyed (report, not a gate)"
if "${ROOT_DIR}/scripts/verify-destroyed.sh"; then
  echo "==> destroy complete; bootstrap stack intact."
else
  echo "WARN: verify-destroyed reported offenders. Inspect output above." >&2
fi
