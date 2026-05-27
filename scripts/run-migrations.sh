#!/usr/bin/env bash
# scripts/run-migrations.sh — invoke the alembic migration task on ECS
# RunTask and exit with the container's exit code.
#
# Reads four outputs from the demo env's Terraform state:
#   cluster_name, migrate_task_definition_arn, task_subnets,
#   task_security_group_id.
#
# Exit codes:
#   0       — alembic upgrade succeeded.
#   <code>  — alembic exited with that non-zero code.
#   124     — timeout (task did not reach STOPPED within MIGRATE_TIMEOUT seconds).
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/envs/demo"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-nica-erp}"
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

MIGRATE_POLL_INTERVAL_SEC="${MIGRATE_POLL_INTERVAL_SEC:-15}"
MIGRATE_TIMEOUT="${MIGRATE_TIMEOUT:-1200}" # 20 minutes

for tool in aws terraform python3; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "ERROR: required tool '${tool}' not found." >&2
    exit 1
  fi
done

echo "==> Reading demo env outputs"
outputs_json="$(terraform -chdir="${TF_DIR}" output -json)"

read_output() {
  echo "${outputs_json}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
val = data['$1']['value']
print(json.dumps(val) if isinstance(val, list) else val)
"
}

cluster_name="$(read_output cluster_name)"
task_def_arn="$(read_output migrate_task_definition_arn)"
subnets_json="$(read_output task_subnets)"
sg_id="$(read_output task_security_group_id)"

if [[ -z "${cluster_name}" || -z "${task_def_arn}" || -z "${subnets_json}" || -z "${sg_id}" ]]; then
  echo "ERROR: missing required terraform output. Did 'terraform apply' run?" >&2
  exit 1
fi

# subnets_json is a JSON array — feed it straight to awsvpcConfiguration.
network_config="awsvpcConfiguration={subnets=${subnets_json},securityGroups=[${sg_id}],assignPublicIp=DISABLED}"

echo "==> ecs run-task"
run_task_json="$(aws ecs run-task \
  --cluster "${cluster_name}" \
  --launch-type FARGATE \
  --task-definition "${task_def_arn}" \
  --network-configuration "${network_config}" \
  --output json)"

task_arn="$(echo "${run_task_json}" | python3 -c "import json,sys; print(json.load(sys.stdin)['tasks'][0]['taskArn'])")"
echo "    task ARN: ${task_arn}"

# ---- Poll until STOPPED -----------------------------------------------------

elapsed=0
while true; do
  if (( elapsed >= MIGRATE_TIMEOUT )); then
    echo "ERROR: migration task ${task_arn} did not reach STOPPED within ${MIGRATE_TIMEOUT}s." >&2
    aws ecs describe-tasks --cluster "${cluster_name}" --tasks "${task_arn}" --output json >&2 || true
    exit 124
  fi

  describe_json="$(aws ecs describe-tasks --cluster "${cluster_name}" --tasks "${task_arn}" --output json)"
  last_status="$(echo "${describe_json}" | python3 -c "import json,sys; print(json.load(sys.stdin)['tasks'][0]['lastStatus'])")"

  if [[ "${last_status}" == "STOPPED" ]]; then
    exit_code="$(echo "${describe_json}" | python3 -c "
import json, sys
task = json.load(sys.stdin)['tasks'][0]
containers = task.get('containers', [])
if not containers:
    print('255')
else:
    code = containers[0].get('exitCode')
    print(code if code is not None else '255')
")"
    stopped_reason="$(echo "${describe_json}" | python3 -c "
import json, sys
task = json.load(sys.stdin)['tasks'][0]
print(task.get('stoppedReason', ''))
")"
    echo "==> Migration finished: lastStatus=STOPPED, exitCode=${exit_code}"
    [[ -n "${stopped_reason}" ]] && echo "    stoppedReason: ${stopped_reason}"
    exit "${exit_code}"
  fi

  echo "    lastStatus=${last_status} (elapsed=${elapsed}s)"
  sleep "${MIGRATE_POLL_INTERVAL_SEC}"
  elapsed=$(( elapsed + MIGRATE_POLL_INTERVAL_SEC ))
done
