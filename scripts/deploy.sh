#!/usr/bin/env bash
# scripts/deploy.sh — orchestrate the full deploy.
#
# 1. Verify credentials.
# 2. Read .deploy-image-tag (build-and-push-image.sh writes it).
# 3. Terraform init+apply on the demo env.
# 4. Run migrations (ECS RunTask via run-migrations.sh).
# 5. Force ECS service redeploy.
# 6. Build + upload SPA (deploy-web.sh).
# 7. Poll /api/healthz with exponential backoff until db:"ok".
#
# Called from .github/workflows/deploy.yml AND from `make deploy-local`
# on a linux/amd64 operator host. The same script runs on both surfaces.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TF_DIR="${ROOT_DIR}/infra/terraform/envs/demo"
DEPLOY_TAG_FILE="${ROOT_DIR}/.deploy-image-tag"

DEPLOY_HEALTH_TIMEOUT="${DEPLOY_HEALTH_TIMEOUT:-300}"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

echo "==> check-credentials"
"${ROOT_DIR}/scripts/check-credentials.sh"

# ---- Image tag --------------------------------------------------------------

if [[ ! -f "${DEPLOY_TAG_FILE}" ]]; then
  echo "ERROR: ${DEPLOY_TAG_FILE} is missing. Run \`make build-image\` first" >&2
  echo "       (or build-and-push-image.sh) so it writes the tag." >&2
  exit 1
fi

image_tag="$(tr -d '[:space:]' < "${DEPLOY_TAG_FILE}")"
if [[ -z "${image_tag}" ]]; then
  echo "ERROR: ${DEPLOY_TAG_FILE} is empty." >&2
  exit 1
fi
echo "==> Image tag: ${image_tag}"

# ---- Terraform apply --------------------------------------------------------

# The s3 backend bucket name is account-suffixed; resolve it once.
account_id="$(aws sts get-caller-identity --query Account --output text)"
state_bucket="nica-erp-tf-state-${account_id}"

echo "==> terraform init (env: demo)"
terraform -chdir="${ENV_TF_DIR}" init -input=false -reconfigure \
  -backend-config="bucket=${state_bucket}"

echo "==> terraform apply (env: demo)"
terraform -chdir="${ENV_TF_DIR}" apply -auto-approve -input=false \
  -var "image_tag=${image_tag}"

# ---- Migrations -------------------------------------------------------------

echo "==> Run migrations (ECS RunTask)"
"${ROOT_DIR}/scripts/run-migrations.sh"

# ---- Force ECS service redeploy --------------------------------------------

cluster_name="$(terraform -chdir="${ENV_TF_DIR}" output -raw cluster_name)"
service_name="$(terraform -chdir="${ENV_TF_DIR}" output -raw service_name)"

echo "==> ecs update-service --force-new-deployment"
aws ecs update-service \
  --cluster "${cluster_name}" \
  --service "${service_name}" \
  --force-new-deployment \
  --output json >/dev/null

# ---- Web deploy -------------------------------------------------------------

echo "==> deploy-web.sh"
"${ROOT_DIR}/scripts/deploy-web.sh"

# ---- Health check -----------------------------------------------------------

cf_domain="$(terraform -chdir="${ENV_TF_DIR}" output -raw cloudfront_distribution_domain)"
healthz_url="https://${cf_domain}/api/healthz"

echo "==> Polling ${healthz_url} (timeout=${DEPLOY_HEALTH_TIMEOUT}s)"

delay=5
delay_cap=30
elapsed=0
last_body=""
last_curl_exit=0

while (( elapsed < DEPLOY_HEALTH_TIMEOUT )); do
  if last_body="$(curl --silent --show-error --fail --max-time 10 "${healthz_url}" 2>&1)"; then
    if echo "${last_body}" | grep -q '"db":"ok"'; then
      echo "==> /api/healthz reports db:ok"
      echo "    ${last_body}"
      echo
      echo "==> Deploy complete: ${healthz_url}"
      exit 0
    fi
  else
    last_curl_exit=$?
  fi

  sleep "${delay}"
  elapsed=$(( elapsed + delay ))
  next_delay=$(( delay * 3 / 2 ))
  if (( next_delay > delay_cap )); then
    delay=${delay_cap}
  else
    delay=${next_delay}
  fi
done

echo "ERROR: /api/healthz did not return db:ok within ${DEPLOY_HEALTH_TIMEOUT}s." >&2
echo "       Last response body:" >&2
echo "${last_body}" >&2
echo "       Last curl exit code: ${last_curl_exit}" >&2
exit 1
