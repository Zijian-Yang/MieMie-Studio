# Phase 7D Self-hosted Release Qualification Plan

> **Execution rule:** Treat every release claim as unproven until current-commit evidence exists. Store only sanitized summaries; credentials, tokens, dumps, environment files, usernames, and private rows never enter Git.

**Goal:** Prove that `pre` can replace `main` as the supported one-server self-hosted release, or identify the exact remaining external blocker without weakening the release definition.

**Release candidate boundary:** The project installs a source-built PostgreSQL-only service bound to `127.0.0.1:<port>`. Operators own HTTPS, DNS, Cloudflare, and reverse proxy configuration. Web administrators manage users, backup policy, Aliyun OSS settings, and generic Webhook settings, but never receive Docker, Git, shell, root, database restore, destructive uninstall, or source-update privileges.

## Task 1: Clean-host and architecture matrix

- [ ] Qualify clean Ubuntu 22.04, Ubuntu 24.04, and Debian 12 hosts from the documented production command.
- [ ] Record host architecture, OS release, Docker/Compose version, install stage result, loopback binding, hidden DB/Redis ports, migration head, non-root identities, health, worker queues, doctor result, backup, and repeat-install preservation.
- [ ] Preserve Ubuntu 24.04 `x86_64` evidence from staging and obtain a complete `arm64` build/runtime result on an Apple Silicon Linux VM.
- [ ] Verify the digest-pinned Node/Python images and exact Python lock resolve on both architectures.
- [ ] Remove qualification VMs or purge test installs only after sanitized evidence is copied locally.

## Task 2: Administrator and member release E2E

- [ ] Run bootstrap/registration-state checks on the current commit.
- [ ] Exercise administrator user create/read/update/disable/enable/password-reset/delete, session revocation, member denial, last-admin/self-disable protection, and audit-log coverage.
- [ ] Verify the management UI routes render in a production browser and contain no host-privileged controls.
- [ ] Clean up synthetic users/sessions according to the soft-delete policy.

## Task 3: Backup, offsite OSS, and Webhook

- [ ] Re-run local custom dump, mode-600 sidecar, retention, isolated restore, and full restore on the current commit.
- [ ] Run a real generic Webhook delivery to a controlled receiver and verify retry/redaction behavior.
- [ ] Query only boolean credential readiness for Aliyun OSS; if approved credentials exist, upload a current-release backup and verify remote metadata/checksum without persisting secrets.
- [ ] If no approved OSS credentials exist, record `blocked_external_credentials` and the exact administrator action required; do not classify local backup as offsite success.

## Task 4: Real provider smoke

- [ ] Query only boolean DashScope/provider readiness and select a disposable test administrator/project without writing credentials to disk or Git.
- [ ] Run one current-release real image generation and one real video generation through normal queue/status paths, respecting provider limits.
- [ ] Verify final status, request/deployment identifiers, worker routing, and OSS persistence when configured.
- [ ] Remove the disposable project/session and record only sanitized task outcomes, durations, model IDs, and persistence booleans.
- [ ] If no approved provider key exists, record the external blocker and keep the release candidate status.

## Task 5: Cloudflare and capacity gates

- [ ] Confirm current-commit local and Cloudflare health, request/deployment headers, API no-store/DYNAMIC behavior, source-IP restriction, and public static asset behavior.
- [ ] Run current-release S1 and conservative S4 locally and through Cloudflare.
- [ ] Run the established W2 platform-only staircase without real provider generation; stop at the first failed gate and retain local/public comparison.
- [ ] Treat non-mainland Cloudflare latency as the target as previously decided; failures must still be classified as application, origin/reverse proxy, or edge/client path.
- [ ] Verify API/Redis/PostgreSQL/workers stay healthy with zero unexpected restarts after load.

## Task 6: Security, documentation, and final release audit

- [ ] Run backend full suite; frontend typecheck, lint, build, chunk/contracts, and browser E2E; installer/CLI/lifecycle/Compose/restore verifiers.
- [ ] Scan tracked files, diffs, artifacts, logs, release state, and browser-visible responses for credentials or private data.
- [ ] Verify no application container is root/privileged, no Docker socket or host management path is mounted, and no Web route exposes host lifecycle/destructive operations.
- [ ] Reproduce README install/update/backup/uninstall steps from a clean environment and correct every mismatch.
- [ ] Update roadmap, phase report, docs entrypoint, changelog, issues, release evidence, and `README.pre.md` with the current commit and exact release classification.
- [ ] Perform a requirement-by-requirement completion audit against the design, ADR-0004, this plan, and the roadmap final definition.

## Release decision

`pre` may be marked **self-hosted release ready** only when every non-external task above has current evidence and both approved provider and Aliyun OSS smokes pass. If credentials are unavailable, all code, local operations, OS matrix, capacity, and security work should still be completed, but the final state remains **release candidate blocked only by named external credentials**.
