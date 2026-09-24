#!/usr/bin/env bash
set -euo pipefail
set +x
# Read-only helper: resolve the same release/manifest and rerun remote checks.
if [[ $# -ne 2 ]]; then
  printf 'DEPLOYMENT BLOCKED: Usage: %s <version> <server>\n' "$0" >&2
  exit 1
fi
command -v python3 >/dev/null 2>&1 || { printf 'DEPLOYMENT BLOCKED: python3 is required.\n' >&2; exit 1; }
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec python3 "$script_dir/deployment.py" verify "$@"
