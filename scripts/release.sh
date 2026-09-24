#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

[[ $# -eq 1 ]] || fail 'Usage: ./scripts/release.sh vMAJOR.MINOR.PATCH'
version=$1
# V1 creates stable releases only: no leading zeros, prerelease or build suffixes.
[[ $version =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] ||
  fail 'Invalid version: expected stable SemVer vMAJOR.MINOR.PATCH (for example v0.1.0).'

command -v git >/dev/null 2>&1 || fail 'git is required.'
command -v gh >/dev/null 2>&1 || fail 'gh is required. Install GitHub CLI first.'
gh auth status >/dev/null 2>&1 || fail 'gh authentication failed. Run gh auth login first.'
inside=$(git rev-parse --is-inside-work-tree 2>/dev/null) || fail 'Run from a git repository.'
[[ $inside == true ]] || fail 'Run from a git repository working tree.'
state=$(git status --porcelain --untracked-files=all 2>/dev/null) || fail 'Unable to inspect working tree.'
[[ -z $state ]] || fail 'The working tree is not clean. Commit or stash changes, including untracked files.'
branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null) || fail 'Only main may create a release; detached HEAD is not supported.'
[[ $branch == main ]] || fail 'Only main may create a release. Switch to main first.'

git fetch origin --tags >/dev/null 2>&1 || fail 'Unable to fetch origin tags. Check remote access and tag conflicts.'
# --quiet distinguishes a missing ref (1) from other errors.
if git show-ref --verify --quiet "refs/tags/$version"; then
  fail 'Release tag already exists. Choose a new version; existing tags are never overwritten.'
else
  status=$?
  [[ $status -eq 1 ]] || fail 'Unable to check existing tags.'
fi
sha=$(git rev-parse --verify 'HEAD^{commit}' 2>/dev/null) || fail 'Unable to resolve HEAD commit SHA.'
git tag -a "$version" "$sha" -m "Release $version" >/dev/null 2>&1 ||
  fail 'Unable to create annotated tag. Check Git identity and signing configuration.'
git push origin "refs/tags/$version" >/dev/null 2>&1 ||
  fail 'Unable to push tag. Local tag is retained; inspect local/remote state before recovery.'
gh release create "$version" --draft --verify-tag --generate-notes >/dev/null 2>&1 ||
  fail 'Unable to create Draft GitHub Release. Pushed tag is retained; inspect GitHub before retrying.'

printf 'Draft release created (not published).\nRelease version: %s\nCommit SHA: %s\n' "$version" "$sha"
