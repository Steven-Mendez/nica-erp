#!/usr/bin/env bash
# scripts/verify-destroyed.sh — after `make destroy`, assert that only
# bootstrap resources remain in the account under tag Project=nica-erp.
#
# Allow-list (per the bootstrap):
#   - S3 buckets       nica-erp-tf-state-<account-id>, nica-erp-web-<account-id>
#   - DynamoDB table   nica-erp-tf-lock
#   - ECR repository   nica-erp
#   - CloudFront       bootstrap-created distribution
#   - IAM OIDC         token.actions.githubusercontent.com
#   - IAM roles        nica-erp-ci-deploy, nica-erp-ci-destroy
#
# Exits non-zero and lists the offending ARNs when anything else
# tagged Project=nica-erp is still alive.
set -euo pipefail

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

account_id="$(aws sts get-caller-identity --query Account --output text)"

RESOURCES_JSON="$(aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=nica-erp \
  --output json)"
export RESOURCES_JSON

python3 - "${account_id}" <<'PYEOF'
import json
import os
import re
import sys

account_id = sys.argv[1]
data = json.loads(os.environ["RESOURCES_JSON"])
arns = [r["ResourceARN"] for r in data.get("ResourceTagMappingList", [])]

ALLOWED_PATTERNS = [
    rf"^arn:aws:s3:::nica-erp-tf-state-{account_id}$",
    rf"^arn:aws:s3:::nica-erp-web-{account_id}$",
    rf"^arn:aws:dynamodb:[^:]+:{account_id}:table/nica-erp-tf-lock$",
    rf"^arn:aws:ecr:[^:]+:{account_id}:repository/nica-erp$",
    rf"^arn:aws:cloudfront::{account_id}:distribution/[A-Z0-9]+$",
    rf"^arn:aws:iam::{account_id}:oidc-provider/token\.actions\.githubusercontent\.com$",
    rf"^arn:aws:iam::{account_id}:role/nica-erp-ci-(deploy|destroy)$",
]

offenders = [a for a in arns if not any(re.match(p, a) for p in ALLOWED_PATTERNS)]
allowed = [a for a in arns if a not in offenders]

print(f"verify-destroyed: allowed={len(allowed)} offenders={len(offenders)}")
for a in sorted(offenders):
    print(f"  OFFENDER {a}")

if offenders:
    print("==> verify-destroyed: FAIL — non-bootstrap resources still tagged Project=nica-erp", file=sys.stderr)
    sys.exit(1)

print("==> verify-destroyed: only bootstrap resources present")
PYEOF
