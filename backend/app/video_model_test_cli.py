"""视频模型真实验证 CLI"""

from __future__ import annotations

import argparse
import asyncio
import json

from app.services.video_model_testing import (
    generate_model_test_manifest,
    run_video_model_verification,
    select_default_user_id,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="视频模型真实验证工具")
    parser.add_argument("--user-id", default="", help="目标用户 ID，留空时自动选择素材最多的用户")
    parser.add_argument("--provider", default="all", choices=["wan", "kling", "vidu", "all"])
    parser.add_argument("--profile", default="test", choices=["test", "production", "both"])
    parser.add_argument("--scope", default="smoke", choices=["smoke", "full"])
    parser.add_argument("--timeout-minutes", type=int, default=20)
    parser.add_argument("--refresh-manifest", action="store_true")
    parser.add_argument("--manifest-only", action="store_true")
    return parser


async def _main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    user_id = args.user_id or select_default_user_id()

    if args.manifest_only:
        manifest = await generate_model_test_manifest(user_id, refresh=True if args.refresh_manifest else False)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    profiles = ["test", "production"] if args.profile == "both" else [args.profile]
    reports = []
    for profile in profiles:
        report = await run_video_model_verification(
            user_id=user_id,
            provider=args.provider,
            key_profile=profile,
            scope=args.scope,
            timeout_minutes=args.timeout_minutes,
            refresh_manifest=True if args.refresh_manifest else False,
        )
        reports.append(report)

    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
