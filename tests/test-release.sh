#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
bash_bin=$(command -v bash)
git_bin=$(command -v git)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Isolate tests from user Git identity, signing, hooks and remote configuration.
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
export GIT_AUTHOR_NAME='Release Test' GIT_AUTHOR_EMAIL='test@example.invalid'
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GH_REPO || true
export GH_TEST_LOG="$work/gh.log"
mkdir "$work/bin"
ln -s "$git_bin" "$work/bin/git"
cat > "$work/bin/gh" <<'MOCK'
#!/bin/bash
set -euo pipefail
printf '%s\n' "$*" >> "$GH_TEST_LOG"
case "$*" in
  'auth status') exit "${GH_TEST_AUTH_STATUS:-0}" ;;
  'release create '*) exit "${GH_TEST_CREATE_STATUS:-0}" ;;
  *) exit 99 ;;
esac
MOCK
chmod +x "$work/bin/gh"

passed=0
setup() {
  repo="$work/repo-$passed"
  remote="$work/remote-$passed.git"
  git init -q --bare "$remote"
  git init -q -b main "$repo"
  cd "$repo"
  printf 'initial\n' > app.txt
  git add app.txt
  git commit -qm initial
  git remote add origin "$remote"
  git push -q -u origin main
  : > "$GH_TEST_LOG"
  unset GH_TEST_AUTH_STATUS GH_TEST_CREATE_STATUS || true
}
run_release() {
  local status=0
  output=$(PATH="$work/bin" "$bash_bin" "$root/scripts/release.sh" "$@" 2>&1) || status=$?
  actual_status=$status
}
expect_failure() {
  local message=$1
  shift
  run_release "$@"
  if [[ $actual_status -eq 0 || "$output" != *"$message"* ]]; then
    printf 'FAIL: expected failure containing %s; status=%s\n%s\n' "$message" "$actual_status" "$output" >&2
    exit 1
  fi
}
no_tag() {
  if git show-ref --verify --quiet refs/tags/v0.1.0; then
    printf 'FAIL: unexpected local tag\n' >&2
    exit 1
  fi
  if [[ -n $(git ls-remote --tags origin) ]]; then
    printf 'FAIL: unexpected remote tag\n' >&2
    exit 1
  fi
  if [[ $(< "$GH_TEST_LOG") == *'release create'* ]]; then
    printf 'FAIL: unexpected release creation\n' >&2
    exit 1
  fi
}
pass() {
  passed=$((passed + 1))
  printf 'PASS: %s\n' "$1"
}

setup
expect_failure 'Usage:'
no_tag
pass 'missing version'

for version in v01.2.3 0.1.0 v1.2 v1.2.3.4 --help 'v1.2.3 bad' v1.2.3-rc.1 v1.2.3+build; do
  setup
  expect_failure 'version' "$version"
  no_tag
  pass "invalid/unsupported version: $version"
done

setup
expect_failure 'Usage:' v0.1.0 extra
no_tag
pass 'extra argument'

for state in untracked modified staged; do
  setup
  case "$state" in
    untracked) touch new.txt ;;
    modified) printf 'change\n' >> app.txt ;;
    staged) printf 'change\n' >> app.txt; git add app.txt ;;
  esac
  expect_failure 'working tree' v0.1.0
  no_tag
  pass "dirty working tree: $state"
done

setup
git checkout -qb feature
expect_failure 'main' v0.1.0
no_tag
pass 'non-main branch'

setup
git checkout -q --detach
expect_failure 'main' v0.1.0
no_tag
pass 'detached HEAD'

setup
git tag v0.1.0
expect_failure 'already exists' v0.1.0
[[ -z $(git ls-remote --tags origin) ]]
pass 'local tag already exists'

setup
git tag v0.1.0
git push -q origin refs/tags/v0.1.0
git tag -d v0.1.0 >/dev/null
expect_failure 'already exists' v0.1.0
[[ $(< "$GH_TEST_LOG") != *'release create'* ]]
pass 'remote tag already exists'

setup
mv "$work/bin/gh" "$work/gh-stub"
expect_failure 'gh is required' v0.1.0
mv "$work/gh-stub" "$work/bin/gh"
no_tag
pass 'gh missing'

setup
export GH_TEST_AUTH_STATUS=1
expect_failure 'gh authentication' v0.1.0
no_tag
pass 'gh unauthenticated'

setup
mv "$work/bin/git" "$work/git-link"
expect_failure 'git is required' v0.1.0
mv "$work/git-link" "$work/bin/git"
no_tag
pass 'git missing'

setup
mkdir "$work/not-a-repo"
cd "$work/not-a-repo"
expect_failure 'git repository' v0.1.0
pass 'outside repository'

setup
git remote set-url origin "$work/nonexistent.git"
expect_failure 'fetch' v0.1.0
if git show-ref --verify --quiet refs/tags/v0.1.0; then
  printf 'FAIL: tag created after fetch failure\n' >&2
  exit 1
fi
[[ $(< "$GH_TEST_LOG") != *'release create'* ]]
pass 'fetch fails before tag creation'

setup
cat > "$remote/hooks/pre-receive" <<'HOOK'
#!/bin/sh
exit 1
HOOK
chmod +x "$remote/hooks/pre-receive"
expect_failure 'push' v0.1.0
git show-ref --verify --quiet refs/tags/v0.1.0
[[ -z $(git ls-remote --tags origin) ]]
[[ $(< "$GH_TEST_LOG") != *'release create'* ]]
pass 'push failure stops release creation'

setup
export GH_TEST_CREATE_STATUS=1
expect_failure 'Draft GitHub Release' v0.1.0
[[ -n $(git ls-remote --tags origin refs/tags/v0.1.0) ]]
[[ "$output" != *'Draft release created'* ]]
pass 'release failure preserves pushed tag without false success'

setup
sha=$(git rev-parse HEAD)
run_release v0.1.0
[[ $actual_status -eq 0 ]]
[[ $(git cat-file -t refs/tags/v0.1.0) == tag ]]
[[ $(git rev-parse 'v0.1.0^{commit}') == "$sha" ]]
[[ $(git --git-dir="$remote" rev-parse 'v0.1.0^{commit}') == "$sha" ]]
[[ $(< "$GH_TEST_LOG") == $'auth status\nrelease create v0.1.0 --draft --verify-tag --generate-notes' ]]
[[ "$output" == *'v0.1.0'* && "$output" == *"$sha"* ]]
pass 'annotated tag, exact commit, remote push and draft release'
printf '\n%s release tests passed.\n' "$passed"
