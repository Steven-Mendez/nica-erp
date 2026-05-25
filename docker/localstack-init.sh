#!/usr/bin/env bash
# Create the S3 bucket, SQS queues, and event bus the app expects to exist by
# name in any local environment. Each `create-*` is best-effort (`|| true`) so
# the script is safe to re-run on container restarts.
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT="000000000000"
ENDPOINT="http://localhost:4566"

aws --endpoint-url="$ENDPOINT" --region "$REGION" s3 mb s3://nica-erp-files || true

aws --endpoint-url="$ENDPOINT" --region "$REGION" sqs create-queue \
  --queue-name notif-queue-dlq >/dev/null || true
aws --endpoint-url="$ENDPOINT" --region "$REGION" sqs create-queue \
  --queue-name audit-queue-dlq >/dev/null || true
aws --endpoint-url="$ENDPOINT" --region "$REGION" sqs create-queue \
  --queue-name notif-queue >/dev/null || true
aws --endpoint-url="$ENDPOINT" --region "$REGION" sqs create-queue \
  --queue-name audit-queue >/dev/null || true

aws --endpoint-url="$ENDPOINT" --region "$REGION" events create-event-bus \
  --name nica-erp >/dev/null || true

echo "[localstack-init] resources ready"
