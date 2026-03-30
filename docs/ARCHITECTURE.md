# 系统架构

## 技术栈

### 后端
| 技术 | 用途 | 版本 |
|------|------|------|
| FastAPI | Web 框架 | 0.100+ |
| Pydantic | 数据验证 | 2.0+ |
| DashScope SDK | 阿里云 AI 服务 | latest |
| httpx | 异步 HTTP 客户端 | latest |
| Pillow | 图像处理 | latest |
| oss2 | 阿里云 OSS SDK | latest |
| bcrypt | 密码哈希 | 4.0+ |
| slowapi | API 限流 | latest |
| pytest | 自动化测试 | 9.0+ |

### 前端
| 技术 | 用途 | 版本 |
|------|------|------|
| React | UI 框架 | 18.x |
| TypeScript | 类型安全 | 5.x |
| Vite | 构建工具 | 5.x |
| Ant Design | UI 组件库（含双主题系统） | 5.x |
| Zustand | 状态管理（含主题持久化） | 4.x |
| React Router | 路由 | 6.x |
| Axios | HTTP 客户端 | latest |

### 主题系统
- 日间模式（蓝白色系）+ 夜间模式（灰金色系）
- Ant Design ConfigProvider 动态切换 `theme.defaultAlgorithm` / `theme.darkAlgorithm`
- `themeStore.ts` 管理主题状态，持久化到 localStorage
- 所有组件通过 `theme.useToken()` 获取当前主题色值
- 详见 [UI_GUIDELINES.md](UI_GUIDELINES.md)

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (React + Vite)                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  Pages   │  │Components│  │  Stores  │  │   Services/API   │ │
│  │ (页面)   │  │ (组件)   │  │ (状态)   │  │   (API 调用)     │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ▼ HTTP/REST
┌─────────────────────────────────────────────────────────────────┐
│                      后端 (FastAPI)                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Middleware (中间件)                       ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   ││
│  │  │    CORS     │  │  Auth(ASGI)│  │  User Context     │   ││
│  │  │  (跨域)     │  │ (纯ASGI)  │  │  (用户上下文)     │   ││
│  │  └─────────────┘  └─────────────┘  └───────────────────┘   ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      Routers (路由)                          ││
│  │  auth | settings | projects | scripts | characters | ...    ││
│  │  studio | video_studio | audio_studio | gallery | audio    ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     Services (服务层)                        ││
│  │  ┌──────────────────┐  ┌──────────────┐  ┌───────────────┐ ││
│  │  │    DashScope     │  │    Storage   │  │    OSS        │ ││
│  │  │  (AI 服务封装)   │  │  (数据存储)  │  │  (文件存储)   │ ││
│  │  └──────────────────┘  └──────────────┘  └───────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      Config (配置)                           ││
│  │  模型配置 | 用户配置 | API 区域配置                          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       外部服务                                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌────────────────┐  ┌─────────────────┐ │
│  │   DashScope API  │  │   阿里云 OSS    │  │   本地文件系统   │ │
│  │  (文生图/视频)   │  │  (图片/视频)   │  │   (JSON 数据)   │ │
│  └──────────────────┘  └────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 请求处理流程

```
用户请求
    │
    ▼
┌──────────────────┐
│   CORS 中间件     │  ← 处理跨域
└──────────────────┘
    │
    ▼
┌──────────────────┐
│   Auth 中间件     │  ← 验证 Token，设置用户上下文
└──────────────────┘
    │
    ▼
┌──────────────────┐
│   Router         │  ← 路由分发
└──────────────────┘
    │
    ▼
┌──────────────────┐
│   Depends        │  ← 依赖注入（获取用户存储服务）
└──────────────────┘
    │
    ▼
┌──────────────────┐
│   Handler        │  ← 业务处理
└──────────────────┘
    │
    ▼
┌──────────────────┐
│   Service        │  ← 调用服务层
└──────────────────┘
    │
    ▼
┌──────────────────┐
│   清除上下文      │  ← 请求结束，清除 ContextVar
└──────────────────┘
```

## 多用户数据隔离

### 数据目录结构

```
backend/data/
├── users.json              # 用户列表（全局）
├── sessions.json           # 会话列表（全局）
├── config.json             # 默认配置（向后兼容）
└── users/
    ├── {user_id_1}/        # 用户 1 专属目录
    │   ├── config.json     # 用户配置（API Key、OSS 等）
    │   ├── projects/       # 项目数据
    │   ├── characters/     # 角色数据
    │   ├── scenes/         # 场景数据
    │   ├── props/          # 道具数据
    │   ├── frames/         # 分镜首帧数据
    │   ├── videos/         # 视频数据
    │   ├── gallery/        # 图库数据
    │   ├── studio/         # 图片工作室数据
    │   ├── video_studio/   # 视频工作室数据
    │   ├── audio_studio/   # 音频工作室数据
    │   ├── voices/         # 自定义音色数据（复刻/设计）
    │   ├── audio/          # 音频库数据
    │   ├── video_library/  # 视频库数据
    │   └── text_library/   # 文本库数据
    └── {user_id_2}/        # 用户 2 专属目录
        └── ...
```

### 上下文传递机制

使用 Python `contextvars` 实现请求级别的用户上下文：

```python
# 1. AuthMiddleware 设置上下文
set_current_user(user_id)
set_user_config_dir(user_data_path)
set_log_user_context(username)

# 2. StorageServiceProxy 自动路由
storage_service._get_service()  # 返回用户专属的 StorageService

# 3. 配置也按用户隔离
get_config()  # 返回用户专属配置

# 4. 请求结束后清除
clear_user_context()
```

## 并发安全

### 原子文件写入

JSON 文件写入使用原子操作模式（`temp → flock LOCK_EX → fsync → os.replace`），确保进程崩溃不会损坏数据文件。涉及文件：
- `storage.py` — `_write_json_with_lock()`
- `config.py` — `_write_with_lock()`
- `user_service.py` — `_save_users()`, `_save_sessions()`

### 文件锁

JSON 文件读写使用 `fcntl.flock`：
- 读取：共享锁 `LOCK_SH`（通过 `_read_json_with_lock()`）
- 写入：排他锁 `LOCK_EX`（通过 `_write_json_with_lock()`）

### 内存锁

- `StorageService` 使用 `threading.RLock` 保护内存操作
- `_storage_cache` 字典使用 `threading.Lock` + double-checked locking 保护
- `get_user_service()` 单例使用 `threading.Lock` + double-checked locking

## 后台任务执行架构

图片工作室的生成端点 (`POST /studio/{id}/generate`) 采用 **后台异步执行** 模式：

1. 端点接收请求后立即返回 `status: "generating"`
2. 通过 `asyncio.create_task()` 启动后台协程执行实际生成
3. 前端通过轮询 `GET /studio/{id}` 获取生成进度

### 用户上下文传递

后台任务需要手动传递 ContextVar（`user_id`, `user_config_dir`），因为 `asyncio.create_task()` 的上下文在请求结束后被中间件清除。

### 同步 API 处理

DashScope 中部分模型只提供同步 API（如 qwen-image-edit 的 `MultiModalConversation.call`），通过 `asyncio.to_thread()` 在线程池中执行，避免阻塞事件循环。

## 音频工作室模块

### 功能
- **文本转语音 (TTS)**：使用 CosyVoice (cosyvoice-v3-flash) 模型合成语音
- **声音复刻**：从音频样本提取音色特征，创建自定义音色
- **声音设计**：通过文本描述生成自定义音色

### 技术实现
- **TTS**: DashScope SDK `SpeechSynthesizer.call()` 非流式调用，`asyncio.to_thread()` 包装
- **声音复刻**: DashScope SDK `VoiceEnrollmentService`，后台轮询 `query_voice()` 等待审核
- **声音设计**: REST API `POST /api/v1/services/audio/tts/customization`（SDK 不支持），`httpx` 异步调用
- 生成的音频自动上传 OSS（或回退到本地 assets）
- 60+ 系统音色，部分支持 Instruct 情感/方言控制

### 文件结构
```
backend/app/
├── models/audio_studio.py         # AudioStudioTask, VoiceProfile 数据模型
├── services/cosyvoice/
│   ├── tts_service.py             # TTS 合成服务
│   └── voice_service.py           # 声音复刻（SDK）+ 声音设计（REST）
├── routers/audio_studio.py        # 音频工作室 API 路由
└── services/storage.py            # 新增 audio_studio / voices CRUD

frontend/src/
├── pages/AudioStudio/
│   └── AudioStudioPage.tsx        # 三 Tab 页面（TTS/复刻/设计）
└── services/api.ts                # audioStudioApi 接口定义
```

## 生产部署架构

### 开发模式 (默认)
- 后端: `uvicorn --reload`（单进程，热重载）
- 前端: `vite dev`（HMR 开发服务器）

### 生产模式 (`./run.sh start --prod`)
- 后端: `gunicorn` + `uvicorn.workers.UvicornWorker`（多 worker）
- 前端: `npm run build` + 静态文件服务
- API 限流: `slowapi`（默认 200 请求/分钟）
- 会话持久化: JSON 文件（跨 worker 共享）

### 自动更新
- `./run.sh auto-update enable`: 通过 cron 每日凌晨 3:00 自动拉取更新
- 更新前自动备份 `backend/data/` 目录
- `./run.sh rollback`: 支持回滚到上一个版本

## 日志系统

### 日志文件
- 位置: `backend/logs/api_YYYYMMDD.log`
- 轮转: 10MB 最大，保留 10 个备份
- 格式: `时间 | 级别 | [用户] 模块:行号 | 消息`

### 日志包含
- 用户上下文（用户名）
- API 请求/响应详情
- DashScope 调用参数和结果
- 错误堆栈

## 自动化测试

### 测试架构
```
backend/tests/
├── __init__.py
├── conftest.py        # fixtures: 隔离数据目录、TestClient、限流器重置
├── test_fixes.py      # 基础修复与安全相关测试
└── test_video_studio_vace.py  # VACE 视频工作室测试
```

使用 `starlette.testclient.TestClient` 直接测试 FastAPI app，无需启动真实服务器。每个测试自动获得隔离的临时数据目录，测试间互不干扰。

### 覆盖范围
- 当前后端共 28 个 pytest 用例
- 认证流程（注册/登录/改密/登出/token验证）
- bcrypt 密码哈希验证
- CORS 配置和 credentials
- 纯 ASGI 中间件（公开路径/受保护路径）
- 项目 CRUD 和级联删除
- 原子写入文件完整性
- 单例线程安全
- 登录/注册限流

## 端口配置

服务端口可通过三种方式自定义：

| 方式 | 示例 | 持久化 |
|------|------|--------|
| CLI 命令 | `./run.sh port backend 9000` | ✅ 写入 `.miemie.conf` |
| 交互菜单 | 网络设置 → 修改端口 | ✅ 写入 `.miemie.conf` |
| 环境变量 | `MIEMIE_BACKEND_PORT=9000` | ❌ 仅当次生效 |

端口变更会影响：
- `run.sh` 中 uvicorn/vite 的启动端口
- `vite.config.ts` 中前端 dev server 端口和 API proxy target
- `main.py` 中 CORS 允许的源

---

*最后更新: 2026-03-29 (安全修复、测试、端口配置)*
