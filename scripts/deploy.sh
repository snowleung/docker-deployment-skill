#!/usr/bin/env bash
set -euo pipefail
# Do not inherit shell tracing while handling deployment configuration.
set +x
if [[ $# -ne 2 ]]; then
  printf 'DEPLOYMENT BLOCKED: Usage: %s <version> <server>\n' "$0" >&2
  exit 1
fi
command -v python3 >/dev/null 2>&1 || { printf 'DEPLOYMENT BLOCKED: python3 is required.\n' >&2; exit 1; }
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec python3 "$script_dir/deployment.py" deploy "$@"
