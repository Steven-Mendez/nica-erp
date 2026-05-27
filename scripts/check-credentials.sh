#!/usr/bin/env bash
# scripts/check-credentials.sh — verify AWS credentials before any
# mutating script runs.
#
# CI path (OIDC):   AWS_ACCESS_KEY_ID is already in env, AWS_PROFILE
#                   is NOT set. The script uses the env credentials.
# Operator host:    the script pins AWS_PROFILE=nica-erp per the
#                   project's profile convention.
#
# Optional check: if AWS_ACCOUNT_ID is exported, the script verifies
# the returned account matches.
set -euo pipefail

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found on PATH." >&2
  exit 1
fi

if ! identity_json="$(aws sts get-caller-identity --output json 2>&1)"; then
  if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    echo "ERROR: 'aws sts get-caller-identity' failed using the env credentials." >&2
  else
    echo "ERROR: 'aws sts get-caller-identity' failed for profile '${AWS_PROFILE}'." >&2
    echo "Configure it with: aws configure --profile ${AWS_PROFILE}" >&2
  fi
  echo "${identity_json}" >&2
  exit 1
fi

actual_account="$(echo "${identity_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])')"

if [[ -n "${AWS_ACCOUNT_ID:-}" ]] && [[ "${actual_account}" != "${AWS_ACCOUNT_ID}" ]]; then
  echo "ERROR: caller account ${actual_account} does not match expected ${AWS_ACCOUNT_ID}." >&2
  exit 1
fi

echo "AWS identity: ${actual_account} (region: ${AWS_REGION})"
