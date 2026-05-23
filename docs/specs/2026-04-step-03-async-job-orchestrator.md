# Step 03：长任务调度从 API 进程迁出

## 标题

把图像、视频、音频等长任务从 `asyncio.create_task` 的 API 进程内模型迁到独立 Worker 队列。

## 背景

- 当前多个 router 都直接在 API 进程里 `create_task`。
- 这种模型在以下场景下不稳：
  - API 进程重启
  - 平滑发布
  - 多实例扩容
  - 长任务积压
  - 任务执行与 API 抢资源
- 平台未来预计会接入更多厂商模型、更多模块和更细粒度任务类型，任务治理复杂度会持续上升。

## 目标

- API 请求快速返回任务记录
- Worker 独立执行长任务
- 任务状态机清晰可追踪
- 支持重试、超时、幂等和回滚

## 非目标

- 本步骤不要求所有业务实体立即迁 PostgreSQL
- 本步骤不要求所有前端页面立即切 SSE

## 方案对比

### 方案 A：继续 `asyncio.create_task`

- 优点：最简单
- 缺点：不可作为稳定生产任务系统

### 方案 B：Celery + Redis

- 优点：
  - 生态成熟
  - 功能丰富
  - 与未来多模块、多厂商、多队列路由的扩展更匹配
  - Redis 也将承担会话、缓存、限流，可减少首期基础设施种类
- 缺点：
  - 对当前偏 async / I/O 密集型任务来说不如 ARQ 自然
  - Worker 集成与任务封装复杂度更高

### 方案 C：Celery + RabbitMQ

- 优点：
  - 队列语义、路由、确认与积压处理通常比 Redis 更强
  - 更适合非常复杂的队列治理
- 缺点：
  - 比 Celery + Redis 多一类基础设施
  - 对当前阶段运维门槛更高

### 方案 D：ARQ + Redis

- 优点：
  - asyncio 原生
  - 与 FastAPI 更贴近
  - 迁移当前 async 调用成本低
- 缺点：
  - 生态规模小于 Celery
  - 对未来复杂任务治理、运维工具、多人协作经验不如 Celery 稳

### 方案 E：RQ

- 优点：简单
- 缺点：
  - 更适合轻量后台作业
  - 对未来复杂重试、路由、调度和治理能力偏弱

### 推荐

- **优先推荐 `Celery + Redis`**
- 保持 broker / task dispatcher 抽象，未来如有更复杂的队列治理需求，再评估切换到 `Celery + RabbitMQ`
- 不建议当前阶段直接选 RQ
- 不建议在没有抽象层的前提下把业务代码直接绑定到 Celery API

## 推荐任务状态机

- `queued`
- `dispatching`
- `provider_running`
- `persisting_assets`
- `succeeded`
- `failed`
- `cancelled`
- `retry_waiting`

## 为什么此阶段更偏向 Celery + Redis

- Celery 在 Python 生态里更成熟，关于重试、路由、监控、运维、异常场景的经验更丰富。
- Redis 在 Step 02 已经是既定依赖，因此首期以 Redis 作为 broker 可以少引入一种基础设施。
- 当前 async 链路与 Celery 的契合度不如 ARQ，这是成本；但这个成本可以通过统一 service / adapter 层封装来控制。
- 如果后续出现：
  - 大量多队列路由
  - 更强的消费确认语义
  - 更复杂的积压治理
  再把 Celery broker 从 Redis 迁到 RabbitMQ，会比“先上 ARQ 再整体迁 Celery”更平滑。

## 实施粒度（建议）

1. 抽象任务提交接口，不让 router 直接依赖 Celery
2. 引入统一任务 envelope 与任务状态机
3. 先用 Redis 作为 Celery broker
4. 图片工作室先试点接队列
5. 验证成功后迁视频工作室
6. 再迁音频工作室与测评任务
7. 最后统一重试/取消/失败分类
8. 视复杂度再评估是否升级到 RabbitMQ broker

## 幂等与重试建议

- 提交任务时生成平台任务 ID
- Worker 端按任务 ID 做幂等保护
- 厂商超时/429/5xx 才自动重试
- 参数错误、权限错误不自动重试

## 实现边界

- 前端：
  - 提交后只关心任务 ID 与状态订阅
- API：
  - 创建任务记录
  - 入队
  - 提供查询与取消入口
- Worker：
  - 真正执行外部调用
  - 按状态机落盘
- 队列基础设施：
  - broker 只负责传递任务，不应成为业务任务状态的唯一真相来源

## 可观测性

- 队列长度
- Worker 并发占用
- 单任务执行时长
- 重试次数
- 失败类型分布
- broker 健康度与连接错误

## 验收标准

- API 重启不会丢失已提交任务记录
- Worker 独立重启不会破坏任务状态一致性
- 至少一个工作室链路完全从 API 进程内任务迁到 Worker
- router / service 层不直接耦合 Celery 原生调用，保留后续 broker 调整空间

## 文档更新

- 任务模型 spec
- 运维手册

## 2026-05-23 最小实装状态

- 新增 Celery app 与 worker task entrypoint。
- 新增统一 `task_dispatcher`，router 不直接依赖 Celery API。
- Compose 新增 `worker` 服务，复用 API 镜像，默认通过 Redis broker 执行图片工作室生成任务。
- 图片工作室 `/generate` 已从直接 `asyncio.create_task` 改为调用 dispatcher：
  - 默认 `MIEMIE_TASK_DISPATCHER=asyncio`，适合本地开发和测试。
  - Compose 默认 `MIEMIE_TASK_DISPATCHER=celery`，将图片生成入队 worker。
- 视频工作室、音频工作室和测评任务仍保留现有后台协程路径，待图片工作室试点验证后再迁。

当前未覆盖：

- 尚未迁移视频工作室。
- 尚未建立完整统一任务 envelope。
- 尚未做 worker 重启恢复、取消、重试分类的全链路验证。

## 讨论重点

- 你更看重：
  - 首期基础设施尽量少
  - 还是一步到位引入更强 broker 语义
- 这会影响我们在 `Celery + Redis` 和 `Celery + RabbitMQ` 之间的后续取舍。
