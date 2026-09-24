#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
bash_bin=$(command -v bash)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export DEPLOY_TEST_LOG="$work/calls"
# Tripwires ensure placeholders do not invoke external deployment tools.
for tool in ssh scp rsync docker git gh curl; do
  cat > "$work/$tool" <<'MOCK'
#!/bin/bash
printf 'unexpected external command\n' >> "$DEPLOY_TEST_LOG"
exit 99
MOCK
  chmod +x "$work/$tool"
done
for script in deploy.sh verify-deployment.sh; do
  status=0
  output=$(PATH="$work" "$bash_bin" "$root/scripts/$script" v0.1.0 production manifest.yaml 2>&1) || status=$?
  [[ $status -eq 1 && "$output" == *'not implemented'* ]]
  [[ ! -e $DEPLOY_TEST_LOG ]]
  printf 'PASS: %s fails explicitly without external commands\n' "$script"
done
printf '\n2 skeleton tests passed.\n'
