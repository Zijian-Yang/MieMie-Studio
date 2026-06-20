#!/usr/bin/env python3
"""Audit the pre-studio public entrypoint without mutating application state."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


ROOT_DIR = Path(__file__).resolve().parents[1]


def env_value(name: str, default: str) -> str:
    return os.environ.get(name, default)


RUN_ID = env_value("RUN_ID", f"pre-studio-entrypoint-audit-{time.strftime('%Y%m%d%H%M%S')}")
ARTIFACT_DIR = Path(
    env_value(
        "ARTIFACT_DIR",
        str(ROOT_DIR / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r125-pre-studio-entrypoint-audit"),
    )
)
CONFIRM = env_value("CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT", "dry-run")
PUBLIC_BASE_URL = env_value("PUBLIC_BASE_URL", "https://pre-studio.miemie.co").rstrip("/")
LOCAL_BASE_URL = env_value("LOCAL_BASE_URL", "").rstrip("/")
EXPECT_CLOUDFLARE = env_value("EXPECT_CLOUDFLARE", "true").lower() in {"1", "true", "yes"}
CONNECT_TIMEOUT = env_value("CONNECT_TIMEOUT", "10")
MAX_TIME = env_value("MAX_TIME", "20")
STATIC_CACHE_MIN_AGE = int(env_value("STATIC_CACHE_MIN_AGE", "604800"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_status(state: str, stage: str, reason: str = "", extra: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "run_id": RUN_ID,
        "state": state,
        "stage": stage,
        "reason": reason,
        "artifact_dir": str(ARTIFACT_DIR),
        "confirm": CONFIRM,
        "public_base_url": PUBLIC_BASE_URL,
        "local_base_url": LOCAL_BASE_URL,
        "expect_cloudflare": EXPECT_CLOUDFLARE,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if extra:
        payload.update(extra)
    write_json(ARTIFACT_DIR / "status.json", payload)


def write_plan() -> None:
    plan = ARTIFACT_DIR / "pre-studio-entrypoint-audit-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "\n".join(
            [
                "# Pre-studio Entrypoint Audit",
                "",
                "Default mode is dry-run.",
                "",
                "Run the read-only audit with:",
                "",
                "```bash",
                "CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT=run python3 scripts/pre_studio_entrypoint_audit.py",
                "```",
                "",
                "Optional server-side local origin check:",
                "",
                "```bash",
                "LOCAL_BASE_URL=http://127.0.0.1:18100 CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT=run python3 scripts/pre_studio_entrypoint_audit.py",
                "```",
                "",
                "The run mode checks:",
                "",
                "- public `/api/health` is 200 and returns `status=ok`, `redis.ok=true`, and `database.ok=true` when present;",
                "- public API headers include `X-Request-ID`, `X-Deployment-Version`, `Cache-Control: no-store`, and Cloudflare `DYNAMIC` cache status;",
                "- public `/` is 200 HTML and references a hashed `/_static/*` asset;",
                "- the hashed static asset has long immutable cache headers and reaches Cloudflare `HIT` on the second request;",
                "- optional local origin `/api/health` is 200 when `LOCAL_BASE_URL` is provided.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def parse_header_blocks(raw: str) -> tuple[int, dict[str, str]]:
    blocks = [block for block in raw.replace("\r\n", "\n").split("\n\n") if block.strip()]
    if not blocks:
        return 0, {}
    lines = blocks[-1].splitlines()
    status_match = re.match(r"HTTP/\S+\s+(\d+)", lines[0])
    status_code = int(status_match.group(1)) if status_match else 0
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return status_code, headers


def curl_request(label: str, url: str) -> dict[str, Any]:
    headers_path = ARTIFACT_DIR / f"{label}.headers"
    body_path = ARTIFACT_DIR / f"{label}.body"
    command = [
        "curl",
        "--noproxy",
        "*",
        "-sS",
        "-D",
        str(headers_path),
        "-o",
        str(body_path),
        "--connect-timeout",
        CONNECT_TIMEOUT,
        "--max-time",
        MAX_TIME,
        url,
    ]
    env = {
        **os.environ,
        "NO_PROXY": "*",
        "no_proxy": "*",
    }
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    result = subprocess.run(command, cwd=ROOT_DIR, check=False, text=True, capture_output=True, env=env)
    header_raw = headers_path.read_text(encoding="utf-8", errors="replace") if headers_path.exists() else ""
    status_code, headers = parse_header_blocks(header_raw)
    return {
        "label": label,
        "url": url,
        "exit_code": result.returncode,
        "status_code": status_code,
        "headers": headers,
        "headers_path": str(headers_path),
        "body_path": str(body_path),
        "stderr": result.stderr.strip(),
    }


def read_json_body(response: dict[str, Any]) -> dict[str, Any]:
    path = Path(response["body_path"])
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_text_body(response: dict[str, Any]) -> str:
    path = Path(response["body_path"])
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def record(results: list[dict[str, str]], failures: list[str], warnings: list[str], check: str, ok: bool, detail: str, warn: bool = False) -> None:
    if ok:
        state = "passed"
    elif warn:
        state = "warning"
        warnings.append(f"{check}: {detail}")
    else:
        state = "blocked"
        failures.append(f"{check}: {detail}")
    results.append({"check": check, "state": state, "detail": detail})


def header_value(response: dict[str, Any], name: str) -> str:
    return response["headers"].get(name.lower(), "")


def check_health(prefix: str, response: dict[str, Any], expect_cloudflare: bool, results: list[dict[str, str]], failures: list[str], warnings: list[str]) -> dict[str, Any]:
    body = read_json_body(response)
    headers = response["headers"]
    record(results, failures, warnings, f"{prefix}_curl", response["exit_code"] == 0, response.get("stderr") or "curl exit 0")
    record(results, failures, warnings, f"{prefix}_http_200", response["status_code"] == 200, f"status={response['status_code']}")
    record(results, failures, warnings, f"{prefix}_status_ok", body.get("status") == "ok", f"body.status={body.get('status')}")
    redis = body.get("redis") if isinstance(body.get("redis"), dict) else {}
    database = body.get("database") if isinstance(body.get("database"), dict) else {}
    record(results, failures, warnings, f"{prefix}_redis_ok", redis.get("ok") is True, f"redis.ok={redis.get('ok')}")
    if database:
        record(results, failures, warnings, f"{prefix}_database_ok", database.get("ok") is True, f"database.ok={database.get('ok')}")
    record(results, failures, warnings, f"{prefix}_request_id", bool(headers.get("x-request-id")), "X-Request-ID present")
    record(results, failures, warnings, f"{prefix}_deployment_version", bool(headers.get("x-deployment-version")), "X-Deployment-Version present")
    cache_control = headers.get("cache-control", "")
    record(results, failures, warnings, f"{prefix}_no_store", "no-store" in cache_control.lower(), f"cache-control={cache_control}")
    if expect_cloudflare:
        record(results, failures, warnings, f"{prefix}_server_cloudflare", headers.get("server", "").lower() == "cloudflare", f"server={headers.get('server', '')}")
        record(results, failures, warnings, f"{prefix}_cf_dynamic", headers.get("cf-cache-status", "").upper() == "DYNAMIC", f"cf-cache-status={headers.get('cf-cache-status', '')}")
    if "h3" in headers.get("alt-svc", "").lower():
        record(results, failures, warnings, f"{prefix}_http3_advertised", False, "alt-svc advertises h3", warn=True)
    return body


def max_age(cache_control: str) -> int:
    match = re.search(r"max-age=(\d+)", cache_control, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def run_audit() -> None:
    write_plan()
    results: list[dict[str, str]] = []
    failures: list[str] = []
    warnings: list[str] = []
    responses: dict[str, dict[str, Any]] = {}

    if CONFIRM != "run":
        write_status("dry_run", "planned", "set CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT=run to execute read-only entrypoint audit")
        print(f"dry-run entrypoint audit plan written to {ARTIFACT_DIR / 'pre-studio-entrypoint-audit-plan.md'}")
        return

    public_health = curl_request("public-health", f"{PUBLIC_BASE_URL}/api/health")
    responses["public_health"] = public_health
    public_body = check_health("public_health", public_health, EXPECT_CLOUDFLARE, results, failures, warnings)

    if LOCAL_BASE_URL:
        local_health = curl_request("local-health", f"{LOCAL_BASE_URL}/api/health")
        responses["local_health"] = local_health
        check_health("local_health", local_health, False, results, failures, warnings)

    public_root = curl_request("public-root", f"{PUBLIC_BASE_URL}/")
    responses["public_root"] = public_root
    root_headers = public_root["headers"]
    root_body = read_text_body(public_root)
    record(results, failures, warnings, "public_root_curl", public_root["exit_code"] == 0, public_root.get("stderr") or "curl exit 0")
    record(results, failures, warnings, "public_root_http_200", public_root["status_code"] == 200, f"status={public_root['status_code']}")
    record(results, failures, warnings, "public_root_html", "text/html" in root_headers.get("content-type", "").lower(), f"content-type={root_headers.get('content-type', '')}")

    static_match = re.search(r"['\"](/_static/[^'\"]+\.(?:js|css))['\"]", root_body)
    static_path = static_match.group(1) if static_match else ""
    record(results, failures, warnings, "public_root_static_asset", bool(static_path), static_path or "no /_static asset found")

    if static_path:
        static_url = urljoin(f"{PUBLIC_BASE_URL}/", static_path.lstrip("/"))
        public_static_first = curl_request("public-static-first", static_url)
        public_static_second = curl_request("public-static-second", static_url)
        responses["public_static_first"] = public_static_first
        responses["public_static_second"] = public_static_second
        for label, response in (("public_static_first", public_static_first), ("public_static_second", public_static_second)):
            headers = response["headers"]
            record(results, failures, warnings, f"{label}_curl", response["exit_code"] == 0, response.get("stderr") or "curl exit 0")
            record(results, failures, warnings, f"{label}_http_200", response["status_code"] == 200, f"status={response['status_code']}")
            record(results, failures, warnings, f"{label}_request_id", bool(headers.get("x-request-id")), "X-Request-ID present")
            record(results, failures, warnings, f"{label}_deployment_version", bool(headers.get("x-deployment-version")), "X-Deployment-Version present")
            cache_control = headers.get("cache-control", "")
            cache_ok = "public" in cache_control.lower() and "immutable" in cache_control.lower() and max_age(cache_control) >= STATIC_CACHE_MIN_AGE
            record(results, failures, warnings, f"{label}_cache_control", cache_ok, f"cache-control={cache_control}")
            if EXPECT_CLOUDFLARE:
                record(results, failures, warnings, f"{label}_server_cloudflare", headers.get("server", "").lower() == "cloudflare", f"server={headers.get('server', '')}")

        second_cf_status = header_value(public_static_second, "cf-cache-status").upper()
        record(results, failures, warnings, "public_static_second_cf_hit", second_cf_status == "HIT", f"cf-cache-status={second_cf_status}")

        health_version = public_body.get("git_commit")
        static_version = header_value(public_static_second, "x-deployment-version")
        if health_version and static_version and health_version != static_version:
            record(
                results,
                failures,
                warnings,
                "deployment_version_match",
                False,
                f"health={health_version} static={static_version}",
                warn=True,
            )

    results_path = ARTIFACT_DIR / "results.tsv"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("w", encoding="utf-8") as handle:
        handle.write("check\tstate\tdetail\n")
        for row in results:
            handle.write(f"{row['check']}\t{row['state']}\t{row['detail']}\n")

    write_json(
        ARTIFACT_DIR / "responses.summary.json",
        {
            key: {
                "url": value["url"],
                "exit_code": value["exit_code"],
                "status_code": value["status_code"],
                "headers": {
                    name: value["headers"].get(name, "")
                    for name in (
                        "server",
                        "cache-control",
                        "cf-cache-status",
                        "cf-ray",
                        "alt-svc",
                        "x-request-id",
                        "x-deployment-version",
                    )
                },
                "headers_path": value["headers_path"],
                "body_path": value["body_path"],
            }
            for key, value in responses.items()
        },
    )

    if failures:
        write_status("blocked", "done", "; ".join(failures), {"warnings": warnings, "failures": failures})
        print(json.dumps(json.loads((ARTIFACT_DIR / "status.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=2))
        raise SystemExit(2)

    state = "passed_with_warnings" if warnings else "passed"
    write_status(state, "done", "entrypoint audit completed", {"warnings": warnings})
    print(json.dumps(json.loads((ARTIFACT_DIR / "status.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_audit()
