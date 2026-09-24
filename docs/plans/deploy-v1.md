# Deploy V1 implementation plan

Scope: Published Release → exact tag commit → commit-owned manifest → read-only plan/precheck → server checkout/build/start → five automatic checks → manual verification pending. No production calls during development.

1. Add isolated local-Git integration fixtures with stub GitHub, SSH, Docker and curl. Exercise actual remote runner locally inside disposable directories; fail on unexpected external calls. Observe existing skeleton failing.
2. Implement Bash entrypoints and a shared Python helper. Use PyYAML SafeLoader locally with duplicate-key rejection and strict schema checks; send validated nonsecret config and the helper through SSH stdin. Remote requires Python 3, Git, Docker Compose, curl and disk inspection; no remote package installation or helper files.
3. Resolve GitHub repository explicitly from origin, validate published release, fetch tag from that repository into a temporary local Git repository and peel it to a commit. Read `.deploy/manifest.yaml` with git show from that commit. Never read working-tree manifest.
4. Print plan before SSH. Precheck remote paths, Git identity/origin, clean tree, dependencies, env names, persistent directories and disk free space. Stop with BLOCKED before mutation. Preserve env and directories outside repository.
5. Fetch remote tags, compare remote tag SHA to expected, detach checkout and compare HEAD. Validate effective Compose JSON without printing it, pin configured service image to release version, stream redacted build/up/ps output, then run shared verifier.
6. Verify commit, running services, env names, directories and health status with bounded readiness retries. Print five PASS results and AWAITING MANUAL VERIFICATION only after all succeed. Separate verification Bash helper reuses read-only remote checks.
7. Update skill/reference/README/template, record dependencies and acceptance steps. Run all release/deploy tests, syntax/schema checks, ShellCheck and independent code review; fix findings and rerun affected checks.
