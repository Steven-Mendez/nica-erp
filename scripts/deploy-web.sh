#!/usr/bin/env bash
# scripts/deploy-web.sh — build the SPA, upload to the SPA bucket,
# invalidate the CloudFront distribution.
#
# Two-call S3 sync so /index.html is no-cache (route updates pick up
# immediately) and the rest of the bundle is far-future cacheable.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_TF_DIR="${ROOT_DIR}/infra/terraform/bootstrap"
WEB_DIR="${ROOT_DIR}/apps/web"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

for tool in aws pnpm; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "ERROR: required tool '${tool}' not found." >&2
    exit 1
  fi
done

# Resolve bootstrap outputs directly from AWS (CI does not have the
# Terraform state backend mounted, and terraform here would be
# over-broad permissions for the deploy role).
echo "==> Resolving bootstrap outputs"
distribution_id="${CLOUDFRONT_DISTRIBUTION_ID:-}"
web_bucket="${WEB_BUCKET:-}"

if [[ -z "${distribution_id}" ]] || [[ -z "${web_bucket}" ]]; then
  if [[ -d "${BOOTSTRAP_TF_DIR}/.terraform" ]]; then
    distribution_id="${distribution_id:-$(terraform -chdir="${BOOTSTRAP_TF_DIR}" output -raw cloudfront_distribution_id)}"
    web_bucket="${web_bucket:-$(terraform -chdir="${BOOTSTRAP_TF_DIR}" output -raw web_bucket)}"
  else
    account_id="$(aws sts get-caller-identity --query Account --output text)"
    web_bucket="${web_bucket:-nica-erp-web-${account_id}}"
    distribution_id="${distribution_id:-$(aws cloudfront list-distributions \
      --query "DistributionList.Items[?Comment=='nica-erp SPA + /api/* placeholder'] | [0].Id" \
      --output text)}"
  fi
fi

if [[ -z "${distribution_id}" ]] || [[ "${distribution_id}" == "None" ]]; then
  echo "ERROR: could not resolve CloudFront distribution ID." >&2
  exit 1
fi
if [[ -z "${web_bucket}" ]]; then
  echo "ERROR: could not resolve SPA bucket name." >&2
  exit 1
fi

echo "    distribution_id: ${distribution_id}"
echo "    web_bucket:      ${web_bucket}"

echo "==> pnpm build (apps/web)"
(cd "${WEB_DIR}" && pnpm install --frozen-lockfile --silent && pnpm build)

echo "==> aws s3 sync (long-cache for assets)"
aws s3 sync "${WEB_DIR}/dist/" "s3://${web_bucket}/" \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"

echo "==> aws s3 cp (no-cache for index.html)"
aws s3 cp "${WEB_DIR}/dist/index.html" "s3://${web_bucket}/index.html" \
  --cache-control "public, max-age=0, must-revalidate"

echo "==> cloudfront origin swap (/api/* → ALB)"
# The bootstrap distribution declares an `api-placeholder` origin pointing
# at `placeholder.invalid`. After the ephemeral stack is up, we patch
# that origin's DomainName to the ALB DNS so `/api/*` reaches ECS. The
# bootstrap is intentionally left as the owner of the distribution
# shape; we only update the one mutable origin attribute.
env_tf_dir="${ROOT_DIR}/infra/terraform/envs/demo"
alb_dns="${ALB_DNS_NAME:-}"
if [[ -z "${alb_dns}" ]] && [[ -d "${env_tf_dir}/.terraform" ]]; then
  alb_dns="$(terraform -chdir="${env_tf_dir}" output -raw alb_dns_name 2>/dev/null || true)"
fi
if [[ -z "${alb_dns}" ]]; then
  echo "ERROR: could not resolve ALB DNS name (no ALB_DNS_NAME env and no terraform output)." >&2
  exit 1
fi

dist_cfg_dir="$(mktemp -d)"
trap 'rm -rf "${dist_cfg_dir}"' EXIT

aws cloudfront get-distribution-config --id "${distribution_id}" \
  > "${dist_cfg_dir}/full.json"
etag="$(jq -r '.ETag' "${dist_cfg_dir}/full.json")"
jq '.DistributionConfig' "${dist_cfg_dir}/full.json" \
  > "${dist_cfg_dir}/config.json"

current_origin="$(jq -r '.Origins.Items[] | select(.Id=="api-placeholder") | .DomainName' "${dist_cfg_dir}/config.json")"
if [[ "${current_origin}" == "${alb_dns}" ]]; then
  echo "    already pointing at ${alb_dns} — skipping update"
else
  echo "    ${current_origin} → ${alb_dns}"
  jq --arg dns "${alb_dns}" \
    '(.Origins.Items[] | select(.Id=="api-placeholder") | .DomainName) = $dns' \
    "${dist_cfg_dir}/config.json" > "${dist_cfg_dir}/patched.json"
  aws cloudfront update-distribution \
    --id "${distribution_id}" \
    --distribution-config "file://${dist_cfg_dir}/patched.json" \
    --if-match "${etag}" \
    --query 'Distribution.Status' --output text >/dev/null
fi

echo "==> cloudfront create-invalidation"
inv_id="$(aws cloudfront create-invalidation \
  --distribution-id "${distribution_id}" \
  --paths "/*" \
  --query "Invalidation.Id" \
  --output text)"

echo "    invalidation_id: ${inv_id}"

echo "==> waiting for invalidation to complete"
aws cloudfront wait invalidation-completed \
  --distribution-id "${distribution_id}" \
  --id "${inv_id}"

echo "==> SPA deploy complete"
