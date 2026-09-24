#!/usr/bin/env bash
set -euo pipefail

# Future interface: ./scripts/deploy.sh <version> <environment> <manifest-path>
# Example: ./scripts/deploy.sh v0.1.0 production ./manifest.yaml
# TODO: Validate the manifest and resolve a Published GitHub Release.
# TODO: Reject drafts, require an existing tag, and resolve its exact commit SHA.
# TODO: Connect to an explicitly configured SSH target and checkout that SHA.
# TODO: Preserve server .env; validate required variable names and directories.
# TODO: Build a release-version image with Docker Compose, then run up -d.
# TODO: Run automatic verification and report pending manual business verification.
# No SSH, server writes, or Docker commands are implemented in this stage.
printf 'Error: deploy is not implemented. Future usage: %s <version> <environment> <manifest-path>\n' "$0" >&2
exit 1
