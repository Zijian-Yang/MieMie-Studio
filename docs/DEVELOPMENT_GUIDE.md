# 开发经验指南

> 本文档总结了项目开发过程中的关键经验和最佳实践，供后续开发参考。

---

## 一、OSS 上传规范

### 核心原则
**所有图片/视频生成服务调用时必须传入 `project_id` 参数**，由服务层统一处理 OSS 上传。

### 问题背景
项目早期多个路由在调用服务时缺少 `project_id` 参数，导致：
- OSS 上传路径错误
- 生成的图片/视频无法正确存储到 OSS

### 影响范围
以下路由文件需要确保传入 `project_id`：
- `backend/app/routers/studio.py` - 图片工作室
- `backend/app/routers/frames.py` - 首帧生成
- `backend/app/routers/characters.py` - 角色生成
- `backend/app/routers/scenes.py` - 场景生成
- `backend/app/routers/props.py` - 道具生成
- `backend/app/routers/styles.py` - 风格生成
- `backend/app/routers/videos.py` - 视频生成
- `backend/app/routers/video_studio.py` - 视频工作室

### 正确示例

```python
# ✅ 正确：传入 project_id
urls = await i2i_service.generate_with_multi_images(
    prompt=task.prompt,
    image_urls=ref_urls,
    negative_prompt=task.negative_prompt,
    n=n,
    project_id=task.project_id  # 必须传入
)

# ❌ 错误：缺少 project_id
urls = await i2i_service.generate_with_multi_images(
    prompt=task.prompt,
    image_urls=ref_urls,
    negative_prompt=task.negative_prompt,
    n=n
)
```

### 服务层 OSS 上传支持情况

| 服务 | 支持 OSS 上传 | 备注 |
|------|--------------|------|
| `TextToImageService` | ✅ | - |
| `ImageToImageService` | ✅ | - |
| `ImageToVideoService` | ✅ | - |
| `TextToVideoService` | ✅ | - |
| `KeyframeToVideoService` | ✅ | - |
| `ReferenceToVideoService` | ✅ | - |
| `QwenImageEditService` | ✅ | 后期添加支持 |

---

## 二、服务层与路由层职责划分

### 服务层职责
- API 调用（DashScope、阿里云等）
- OSS 上传处理
- 任务状态轮询
- 结果数据转换

### 路由层职责
- 请求参数验证
- 权限检查
- 调用服务层
- 响应数据组装

### 避免的问题
**不要在路由层重复 OSS 上传逻辑**，这会导致：
- 重复上传同一文件
- 代码冗余
- 维护困难

```python
# ❌ 错误：路由层重复上传
result = await service.generate(prompt, project_id=project_id)
if oss_service.is_enabled():
    oss_url = oss_service.upload_image(result, project_id)  # 服务层已处理！

# ✅ 正确：服务层统一处理，路由层直接使用
result = await service.generate(prompt, project_id=project_id)
# result 已经是 OSS URL（如果启用了 OSS）
```

---

## 三、并发安全规范

### 原子文件写入

所有 JSON 文件写入必须使用原子操作模式，防止进程崩溃导致文件损坏：

```python
import os, fcntl

def _write_json_with_lock(self, file_path, data):
    """原子写入：写入临时文件 → flock → fsync → os.replace"""
    tmp_path = file_path.with_suffix('.tmp')
    with open(file_path, 'r') as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(file_path))
```

**关键点**：
- `os.replace()` 是原子操作（POSIX），要么完全替换要么不替换
- `os.fsync()` 确保数据真正写入磁盘
- `fcntl.flock(LOCK_EX)` 防止并发写入冲突
- 读操作使用 `fcntl.flock(LOCK_SH)` 共享锁

### 文件锁使用规则
- **所有写入**使用 `_write_json_with_lock` (LOCK_EX 排他锁)
- **所有读取**使用 `_read_json_with_lock` (LOCK_SH 共享锁)
- 不要直接 `open()` 读写 JSON 文件

---

## 四、部署指南

### 后端启动
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动
```bash
cd frontend
npm run dev -- --host
```

或在 `vite.config.ts` 中配置：
```typescript
server: {
  host: '0.0.0.0',
  port: 3000,
  // ...
}
```

### 后台运行（使用 screen）
```bash
# 后端
screen -S backend
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Ctrl+A, D 分离

# 前端
screen -S frontend
cd frontend && npm run dev -- --host
# Ctrl+A, D 分离

# 查看运行中的会话
screen -ls

# 重新连接
screen -r backend
screen -r frontend
```

### 云服务器安全组配置
如果部署在阿里云 ECS 等云服务器上：
- 放行 TCP 3000 端口（前端）
- 后端 8000 端口通过 Vite 代理访问，无需对外开放

---

## 五、安全规范

### 敏感信息处理
以下文件包含敏感信息，**绝不能提交到 Git**：
- `backend/data/config.json` - API Key、OSS 密钥
- `backend/data/users.json` - 用户密码
- `backend/data/sessions.json` - 会话 token
- `backend/data/users/` - 用户私有数据
- `text_to_image_config.json` - API Key

### 配置示例文件
提供 `*.example.json` 作为配置模板，真实配置通过复制创建：
```bash
cp backend/data/config.example.json backend/data/config.json
# 编辑 config.json 填入真实密钥
```

### API Key 泄露处理
如果发现 API Key 已泄露：
1. 立即在阿里云控制台禁用/删除该 Key
2. 创建新的 API Key
3. 更新本地配置文件
4. 如果已提交到 Git，使用 `git-filter-repo` 清理历史

---

## 六、模型集成规范

### 新模型接入先看统一范式

工作室类模型（图片/视频/音频）不建议继续按“`config.py + 路由分支 + 页面硬编码 if/else`”的老方式扩展。

优先阅读：
- `docs/STUDIO_MODEL_INTEGRATION_GUIDE.md`

统一原则：
- 先按能力映射 `task_kind`
- 前端先做 canonical request
- 后端 adapter 负责映射厂商 payload
- `preview-payload` 与真实提交共用 builder
- 开发者模式必须能看到 canonical 请求和厂商请求体

### 添加新模型步骤
1. 阅读官方文档，整理能力、素材位、参数、尺寸/分辨率、限制条件
2. 确认该模型应该复用现有 `task_kind` 还是新增能力
3. 在 schema / capabilities 中补齐：
   - 输入素材角色
   - 参数定义
   - 结构化帮助
   - 条件逻辑
4. 在 adapter / service 中补齐：
   - `validate`
   - `build_payload`
   - `submit`
   - `fetch`
   - `normalize_result`
5. 确保服务支持 `project_id` 参数和 OSS 转存
6. 更新前端 API 类型、动态表单和开发者模式
7. 补齐自动化测试与文档

### 模型参数传递
- 前端先提交平台统一语义的 canonical request
- 路由层不应硬编码模型参数
- adapter 负责把 canonical request 映射成厂商 payload
- 前端配置优先从后端 API / capabilities 获取

---

## 七、视频工作室帮助与稳定性规范

### 参数帮助必须随 schema 一起返回

视频工作室的参数解释、限制、选项差异说明，不要散落在前端页面里硬编码。

正确做法：
- 在 `backend/app/services/video_capabilities.py` 中维护参数帮助
- 前端通过 `/api/video-studio/capabilities` 统一获取
- 页面只负责渲染，不负责重新发明帮助文案

### 前端帮助组件统一使用 Popover

问号悬浮说明统一使用 **Popover**，不是短 Tooltip。

原因：
- 视频模型参数说明通常较长
- 需要展示“含义 / 限制 / 怎么选 / 示例”
- Tooltip 不适合承载结构化内容

### 参数迁移提示的触发时机

切模型时，平台会尝试保留兼容参数并重置不兼容参数。

正确触发时机：
- 仅用户主动切换模型时提示

不要提示的场景：
- 创建弹窗首次打开
- 编辑弹窗首次加载
- 切任务类型时切到默认模型
- 代码内部自动回退默认模型

否则很容易出现重复通知，影响体验。

### Wan 局部编辑的参考图用途开关

当前不要给 `video_edit_local` 暴露 `obj/bg` 开关。

原因：
- 本地官方文档只在 `image_reference` 里公开了 `obj_or_bg`
- `video_edit` 没有把它列成公开参数
- 对未公开参数做前端暴露会增加行为不一致和联调风险

---

## 七、常见问题

### Q: 生成的图片/视频无法显示
**可能原因**：
1. OSS 未启用或配置错误
2. 调用服务时未传 `project_id`
3. OSS 链接过期

**排查步骤**：
1. 检查 `backend/data/config.json` 中 OSS 配置
2. 检查服务调用是否传入 `project_id`
3. 检查控制台日志中的 OSS 上传信息

### Q: 图片测评导入线上后 wan2.7 出现 `unsupported`

**背景**：图片测评数据集导出的是 JSON，其中只包含输入图 URL，不包含图片文件本体。跨环境导入时，如果原 URL 是临时链接、内网链接、需要鉴权的链接，或线上机器偶发下载失败，wan2.7 前置图片预检会把该单元标为 `unsupported`。

**开发规范**：
1. 导入跨环境数据集时优先开启 `migrate_images_to_oss`，将输入图重新落到当前用户 OSS。
2. `unsupported` 不应简单理解为“模型不支持”，也可能是输入图读取/解码暂时失败。
3. wan2.7 图片预检错误必须包含 URL 摘要、HTTP 状态或解码原因，不能吞掉异常。
4. 测评单元结果必须保留所有 `task_ids` 和 `request_ids`，自动重试时要累计所有尝试的追踪 ID。

**线上排查命令**：

```bash
jq -r '
  .id as $run
  | .dataset_id as $dataset
  | .cell_results[]?
  | select(.status=="unsupported")
  | [$run, $dataset, .case_id, .case_name, .model_id, (.error_message // "")]
  | @tsv
' backend/data/users/*/image_benchmark_runs/*.json
```

拿到 `run_id` 和 `case_id` 后，查看该样例实际使用的图：

```bash
RUN_ID="..."
CASE_ID="..."
jq -r --arg case "$CASE_ID" '
  .dataset_snapshot.items[]
  | select(.id==$case)
  | .name as $case_name
  | (.image_slots // [] | sort_by(.position)[])
  | [$case_name, (.position|tostring), (.image.name // ""), (.image.url // "")]
  | @tsv
' backend/data/users/*/image_benchmark_runs/${RUN_ID}.json
```

然后在同一台线上机器上验证 URL：

```bash
curl -I -L -s "图片URL"
```

### Q: 并发生成时数据错乱
**可能原因**：存储操作未使用文件锁

**解决方案**：确保所有 JSON 写入操作使用 `_write_json_with_lock`

### Q: 前端无法访问后端 API
**可能原因**：
1. 后端未启动
2. Vite 代理配置错误
3. 端口被占用

**排查步骤**：
1. 确认后端在 8000 端口运行
2. 检查 `vite.config.ts` 中的 proxy 配置
3. 使用 `lsof -i :8000` 检查端口占用

---

## 更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-03-28 | 新增密码安全、认证中间件、限流、测试、端口配置章节；更新原子写入规范 |
| 2025-01-31 | 创建文档，总结 OSS 上传、服务架构、部署等经验 |

---

## 八、密码安全

### bcrypt 哈希
用户密码使用 bcrypt 哈希存储（`backend/app/services/user_service.py`）：

```python
import bcrypt

# 注册时哈希
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# 登录时验证
bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
```

### 渐进式迁移
早期版本使用明文密码。`login()` 方法在验证密码时检测到明文会自动升级为 bcrypt：

```python
if not self._is_hashed(user_data.get('password', '')):
    user_data['password'] = self._hash_password(password)
    # 保存到文件，下次登录直接用 bcrypt
```

判断逻辑：密码以 `$2b$` 或 `$2a$` 开头即为 bcrypt 哈希。

---

## 九、认证中间件

### 纯 ASGI 实现
认证中间件位于 `backend/app/middleware/auth.py`，使用纯 ASGI 协议而非 Starlette 的 `BaseHTTPMiddleware`。

**选择原因**：`BaseHTTPMiddleware` 内部使用 anyio task group，会导致 `contextvars` 在并发请求间泄漏，破坏多用户数据隔离。

**实现要点**：
- 直接实现 `__init__(self, app: ASGIApp)` + `async def __call__(self, scope, receive, send)`
- 从 `scope["headers"]` 中手动解析 Authorization header（bytes→str）
- 用户信息注入到 `scope["state"]` 中（供 FastAPI 的 `request.state` 使用）
- `set_user_context()` / `clear_user_context()` 在 `try/finally` 中确保清理
- 错误响应通过 `_send_json_response()` 直接发送 ASGI message

---

## 十、接口限流

### slowapi 使用规范
限流使用 `slowapi` 库（`backend/app/routers/auth.py`）：

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")
async def login(data: UserLoginRequest, request: Request):
    ...
```

**重要**：slowapi 装饰器通过参数名 `request` 查找 `starlette.requests.Request` 对象。如果 Pydantic 模型参数也叫 `request`，会导致 500 错误。**解决方案**：Pydantic 模型参数用 `data`，Request 参数用 `request`。

---

## 十一、自动化测试

### 运行测试
```bash
./run.sh test                      # 推荐：通过管理脚本运行
cd backend && python -m pytest tests/ -v  # 直接运行
```

### 测试架构
```
backend/tests/
├── __init__.py
├── conftest.py      # pytest fixtures：隔离数据目录、TestClient、限流器重置
├── test_fixes.py    # 基础修复与安全相关测试
└── test_video_studio_vace.py  # VACE 视频工作室测试
```

### 隔离机制（conftest.py）
每个测试用例自动：
1. 创建临时数据目录（`tmp_path`），不影响真实数据
2. 重置 `UserService` 单例，指向临时目录
3. 重置 slowapi 限流计数器，避免测试间干扰

### 添加新测试
当前后端共 28 个 pytest 用例。

在 `test_fixes.py` 或 `test_video_studio_vace.py` 中添加新的测试类或方法，遵循现有模式：
- 需要认证的测试使用 `auth_header` fixture
- 需要已注册用户的使用 `registered_user` fixture
- 限流相关测试放在文件末尾

---

## 十二、自定义端口

### 三种配置方式

**1. CLI 命令（持久化）**
```bash
./run.sh port backend 9000    # 修改后端端口
./run.sh port frontend 3001   # 修改前端端口
./run.sh port                 # 查看当前端口
```

**2. 交互菜单**
`./run.sh` → 网络设置 → 修改端口

**3. 环境变量（临时覆盖）**
```bash
MIEMIE_BACKEND_PORT=9000 MIEMIE_FRONTEND_PORT=3001 ./run.sh start
```

### 配置传递链路
```
.miemie.conf (BACKEND_PORT/FRONTEND_PORT)
  ↓ run.sh 读取
  ↓ 传入 uvicorn --port / npm run dev --port
  ↓ export MIEMIE_FRONTEND_PORT → 后端 CORS 配置
  ↓ vite.config.ts 读取 → proxy target / server.port
```

端口范围限制：1024-65535，前后端端口不能相同。

---

*如有新的开发经验，请在此文档中补充。*
