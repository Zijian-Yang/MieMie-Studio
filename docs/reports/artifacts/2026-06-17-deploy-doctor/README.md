# R54 Deploy Doctor

2026-06-17 added a read-only deployment doctor for Mac and single-server setup checks.

## New Entry Points

- `scripts/deploy_doctor.sh`
- `scripts/verify_deploy_doctor.py`
- `./run.sh doctor`

The doctor does not install dependencies, start services, edit config files, or touch user data. It writes a deployment readiness summary to `status.json` and `results.tsv` under `ARTIFACT_DIR`; by default this is `/tmp/<run_id>/artifacts`.

## Checks

The default profile is `DOCTOR_PROFILE=all` and covers:

- core commands: Git, Python, Node.js, npm, curl, screen, lsof;
- Python `3.10+` and Node.js `18+`;
- required repository files for script and Compose deployment paths;
- sensitive tracked files under `backend/data/`;
- `compose.env` presence and placeholder checks;
- Docker CLI and Docker Compose v2 availability;
- optional Docker daemon check via `MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO=true`;
- local app port occupancy.

For Compose-only readiness, run:

```bash
DOCTOR_PROFILE=compose ./run.sh doctor
```

For host daemon readiness too:

```bash
MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO=true ./run.sh doctor
```

## Local Evidence

Command:

```bash
RUN_ID=r54-deploy-doctor-live-20260617 ARTIFACT_DIR=/tmp/r54-deploy-doctor-live TMP_DIR=/tmp/r54-deploy-doctor-live-tmp ./run.sh doctor
```

Result: `passed_with_warnings`.

Summary:

- passed: 19
- warnings: 2
- blocked: 0
- failed: 0

Warnings:

- `compose.env` is missing; copy `compose.env.example` first for Compose deployment.
- Docker daemon check was skipped by default; set `MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO=true` when validating the host daemon.

No sensitive backend data files are tracked.

## Verification

- `bash -n run.sh`: passed.
- `bash -n scripts/deploy_doctor.sh`: passed.
- `python3 scripts/verify_deploy_doctor.py`: passed.
- `./run.sh help` lists `doctor`.
- `./run.sh doctor` completed with no blocked checks.
