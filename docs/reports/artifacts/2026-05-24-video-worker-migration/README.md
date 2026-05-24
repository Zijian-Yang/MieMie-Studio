# 2026-05-24 视频工作室 Worker 迁移本地验证

本目录用于归档视频工作室 Worker 迁移 v1 的脱敏验证证据。

## 本地验证

```text
venv/bin/pytest backend/tests/test_video_studio_capabilities.py -q
57 passed in 10.22s

./run.sh test
230 passed in 70.81s

cd frontend && npm run typecheck
通过

cd frontend && npm run lint
通过

cd frontend && npm run build
通过；3156 modules transformed，built in 3.22s
提示：Browserslist/caniuse-lite 数据约 6 个月未更新

docker compose config
通过；包含 worker/studio 与 worker-video/video_studio 队列隔离
```

## 待补服务器 artifact

- `pre` 部署后 health / root / celery registered 摘要。
- 无 key或错误 key 视频 worker 失败路径摘要。
- `worker-video` restart 恢复或 stale 兜底摘要。
- 1 个低频真实 DashScope 视频 smoke 摘要。

所有后续 artifact 必须脱敏，不记录 API key、token、密码或真实生成视频 URL。
