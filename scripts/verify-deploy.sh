#!/usr/bin/env bash
# scripts/verify-deploy.sh — post-deploy smoke test against CloudFront.
#
# Resolves the CloudFront domain, curls /api/healthz, asserts the JSON
# body contains db:"ok" and a non-null alembic_revision, then curls
# the SPA root and asserts an HTML response. Exits 0 on success.
#
# Used by `make verify`. Safe to run repeatedly — does not mutate AWS.
set -euo pipefail

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_TF_DIR="${ROOT_DIR}/infra/terraform/bootstrap"

# ---- Resolve CloudFront domain --------------------------------------------

if [[ -n "${CLOUDFRONT_DISTRIBUTION_DOMAIN:-}" ]]; then
  domain="${CLOUDFRONT_DISTRIBUTION_DOMAIN}"
elif [[ -d "${BOOTSTRAP_TF_DIR}/.terraform" ]]; then
  domain="$(terraform -chdir="${BOOTSTRAP_TF_DIR}" output -raw cloudfront_distribution_domain)"
else
  domain="$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='nica-erp SPA + /api/* placeholder'] | [0].DomainName" \
    --output text)"
fi

if [[ -z "${domain}" || "${domain}" == "None" ]]; then
  echo "ERROR: could not resolve CloudFront domain. Has \`make bootstrap\` been run?" >&2
  exit 1
fi

healthz_url="https://${domain}/api/healthz"
spa_url="https://${domain}/"

echo "==> Domain: ${domain}"

# ---- /api/healthz ---------------------------------------------------------

echo "==> GET ${healthz_url}"
healthz_body="$(curl --silent --show-error --fail --max-time 10 "${healthz_url}")" || {
  echo "ERROR: /api/healthz returned non-2xx." >&2
  exit 1
}

echo "${healthz_body}" | python3 -c "
import json
import sys

body = json.loads(sys.stdin.read())
errors = []

if body.get('db') != 'ok':
    errors.append(f\"  db: expected 'ok', got {body.get('db')!r}\")
if not body.get('alembic_revision'):
    errors.append(f\"  alembic_revision: expected non-null, got {body.get('alembic_revision')!r}\")
if body.get('status') != 'ok':
    errors.append(f\"  status: expected 'ok', got {body.get('status')!r}\")

print('healthz response:')
print(json.dumps(body, indent=2))

if errors:
    print()
    print('FAIL — assertions failed:', file=sys.stderr)
    for e in errors:
        print(e, file=sys.stderr)
    sys.exit(1)
"

# ---- SPA root --------------------------------------------------------------

echo "==> GET ${spa_url}"
spa_status_and_type="$(curl --silent --show-error --max-time 10 \
  -o /dev/null \
  -w '%{http_code} %{content_type}' \
  "${spa_url}")"

http_code="${spa_status_and_type%% *}"
content_type="${spa_status_and_type#* }"

if [[ "${http_code}" != "200" ]]; then
  echo "ERROR: SPA root returned HTTP ${http_code} (expected 200)." >&2
  exit 1
fi

if [[ "${content_type}" != text/html* ]]; then
  echo "ERROR: SPA root returned Content-Type '${content_type}' (expected text/html...)." >&2
  exit 1
fi

echo "    HTTP ${http_code}, ${content_type}"
echo
echo "==> Verify-deploy: PASS"
echo "    SPA:     ${spa_url}"
echo "    healthz: ${healthz_url}"
