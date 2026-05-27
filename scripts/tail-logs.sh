#!/usr/bin/env bash
# scripts/tail-logs.sh — follow the API CloudWatch Logs group.
set -euo pipefail

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"

exec aws logs tail /nica-erp/api --follow --since 5m --format short
