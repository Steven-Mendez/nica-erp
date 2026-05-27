#!/usr/bin/env bash
# scripts/print-urls.sh — print the public URLs of the demo env.
#
# Reads the bootstrap CloudFront domain. Convenience for "what URL am I
# pointing at" without diving into the AWS console.
set -euo pipefail

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_TF_DIR="${ROOT_DIR}/infra/terraform/bootstrap"

if [[ -d "${BOOTSTRAP_TF_DIR}/.terraform" ]]; then
  domain="$(terraform -chdir="${BOOTSTRAP_TF_DIR}" output -raw cloudfront_distribution_domain)"
else
  domain="$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='nica-erp SPA + /api/* placeholder'] | [0].DomainName" \
    --output text)"
fi

if [[ -z "${domain}" || "${domain}" == "None" ]]; then
  echo "ERROR: could not resolve CloudFront domain. Has bootstrap been applied?" >&2
  exit 1
fi

echo "SPA:     https://${domain}/"
echo "healthz: https://${domain}/api/healthz"
