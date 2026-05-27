#!/usr/bin/env bash
# scripts/confirm-destroy.sh — interactive confirmation helper.
#
# Usage:  scripts/confirm-destroy.sh <expected-string>
# Exits non-zero unless the operator types <expected-string> exactly.
#
# Sourced by destroy.sh and destroy-bootstrap.sh so the prompt logic
# is not duplicated.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <expected-confirmation-string>" >&2
  exit 2
fi

expected="$1"

echo "Type '${expected}' to confirm destruction (or Ctrl-C to abort):"
read -r typed

if [[ "${typed}" != "${expected}" ]]; then
  echo "ERROR: confirmation mismatch — got '${typed}', expected '${expected}'." >&2
  exit 1
fi
