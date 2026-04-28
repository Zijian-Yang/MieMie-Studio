# 变更日志

> 记录平台的重要变更、新功能和 Bug 修复。
> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

## [Unreleased]

### 安全 (Security)
- **密码哈希**: 用户密码从明文存储改为 bcrypt 哈希，新注册用户自动使用 bcrypt，已有明文密码在首次登录时自动迁移
- **认证中间件**: 从 Starlette `BaseHTTPMiddleware` 重写为纯 ASGI 实现，修复 `contextvars` 在并发请求间泄漏的问题
- **原子文件写入**: `storage.py`、`config.py`、`user_service.py` 的 JSON 写入改为 temp→fsync→os.replace 原子操作，防止进程崩溃导致数据文件损坏
- **CORS 配置**: 从硬编码改为环境变量 `MIEMIE_CORS_ORIGINS` 驱动，修复 `origins=["*"]` + `credentials=True` 违反 CORS 规范的问题
- **接口限流**: 登录接口添加 slowapi 限流 5次/分钟，注册接口 3次/分钟，防止暴力破解

### 新增 (Added)
- 视频测评首帧生视频模块：
  - 侧边栏新增 `视频数据集` 与 `视频测评`
  - 新增 `/api/video-benchmark/*`，独立保存 video benchmark datasets / suites / runs
  - v1 自动筛选所有支持 `image_to_video` 的视频工作室模型，复用 video adapter 构造 payload、提交和轮询
  - 数据集样例支持首帧图、可选驱动音频和可选样例级 `duration`
  - 视频数据集页补齐图片数据集同级批量能力，支持行多选、批量导入首帧或 prompt、批量填充首帧、批量编辑字段、选中排序和删除
  - 视频数据集允许暂存缺首帧样例，保存/导入返回 warnings，运行测评和 payload preview 前阻断缺首帧
  - 视频测评模型参数新增 `生成数量`，支持每个 case × model 单元生成 1-5 条视频，并在矩阵和详情中展示多条输出
  - 运行矩阵展示输出视频，详情保留 effective params、canonical request、provider payload、provider result meta、task/request id
  - Markdown / HTML 报告导出保留视频 URL，不内嵌视频字节
- 图片测评导出支持内嵌图片资源：
  - `导出 Markdown` 与 `导出 HTML` 统一改为后端生成
  - 导出时会把输入图 / 输出图下载并转成 `data:` 内嵌到单文件中
  - 导出页新增“快速导出”，可跳过内嵌、直接保留原 URL
  - 新增 `export-md-file / export-html-file` 附件接口，前端直接下载文件而非传超大 JSON
  - 响应新增 `embedded_image_count` 与 `fallback_url_count`
- 管理脚本运行时可观测性：
  - `GET /api/health` 新增 `git_commit`、`run_mode`、`serve_frontend`、`started_at`
  - `./run.sh status` / TUI 状态栏新增默认模式、实际模式、当前运行提交与前端服务方式
- 图片测评数据集导入增强：
  - `POST /api/image-benchmark/datasets/import` 新增 `migrate_images_to_oss` 参数
  - 跨环境导入时可将输入图下载并重新上传到当前用户 OSS
  - 响应返回 `migration_report`，包含转存成功、失败、跳过数量和失败明细
- 图片测评支持 wan2.7 交互式编辑：
  - 新增 `interactive_edit` 测评任务类型
  - 数据集样例新增 `bbox_list`，导入/导出/保存均保留框选数据
  - 数据集编辑弹窗复用图片工作室画框组件，可对每个输入图绘制最多 2 个框
  - 测评运行时会将 bbox 归一化后传入 wan2.7 provider payload
- 图片测评单元详情增强：
  - 单元详情弹窗展示完整 `task_ids` 与 `request_ids`
  - 自动重试时会累计每次尝试产生的所有 task/request id
  - `provider_result_meta.auto_retry` 同步记录累计后的追踪 ID
- 视频工作室参数帮助升级：
  - 所有视频工作室前端可见关键参数支持结构化帮助信息
  - 问号悬浮说明从短 Tooltip 升级为 Popover
  - 帮助内容统一包含“概览 / 含义 / 限制 / 怎么选 / 示例 / 补充说明”
- 视频工作室帮助体系：
  - `video_capabilities.py` 新增参数级 `help`
  - `ui_hints.asset_help` 和 `ui_hints.prompt_help` 升级为结构化帮助
  - Kling / Vidu / Wan 的关键参数和素材位说明统一由后端 schema 下发
- 视频工作室：临时接入 `wan2.7-i2v-2026-04-25` 快照模型
  - 与长期主用 `wan2.7-i2v` 并存，不作为别名、不替换默认模型
  - 支持图生视频、首尾帧生视频和视频续写，复用 wan2.7 i2v 新版 `video-synthesis` 请求结构
  - 开发者模式和真实提交 payload 保留用户选择的独立模型 ID，便于对比快照效果
- 视频工作室：接入 `wanx2.1-vace-plus`
  - 新增 `video_repainting` 视频重绘任务类型
  - 新增 `video_edit` 局部编辑任务类型
  - 后端新增 `VaceVideoEditService`，统一处理任务提交、轮询和结果视频 OSS 回传
  - 视频工作室新增 `POST /video-studio/prepare-source-video` 和 `POST /video-studio/upload-mask` 接口
  - 局部编辑 Mask 编辑器支持画笔、橡皮擦，以及“逐点连线 + Enter 闭环”的多边形模式
- 视频尾帧提取功能：
  - 视频工作室：每个生成视频下方新增"保存尾帧"按钮，使用 ffmpeg 提取最后一帧保存到图库
  - 分镜首帧：当上一个镜头已有视频时，显示"上一视频尾帧"按钮，一键提取并设为当前镜头首帧
  - 后端新增 `POST /video-studio/{id}/extract-last-frame` 和 `POST /frames/set-from-video-last-frame` 两个 API
  - 使用 ffmpeg/ffprobe 提取视频尾帧，上传 OSS 后保存到图库
- 结果标记功能：图片工作室、视频工作室、音频工作室均支持对生成结果添加星标/红旗/对号/红叉标记
  - 图片工作室：每张生成图片下方显示标记按钮，标记保存在 `StudioTaskImage.markers` 字段
  - 视频工作室：每个生成视频下方显示标记按钮，标记保存在 `VideoStudioTask.video_markers` 字典
  - 音频工作室：每条任务历史标题行显示标记按钮，标记保存在 `AudioStudioTask.markers` 字段
  - 后端新增 `POST /studio/{id}/markers`、`POST /video-studio/{id}/markers`、`POST /audio-studio/{id}/markers` 三个 API
- React ErrorBoundary 组件：JS 运行时错误不再导致白屏，显示友好提示和刷新按钮
- pytest 自动化测试：28 个测试用例覆盖认证、bcrypt、CORS、中间件、级联删除、原子写入、单例安全、限流，以及 VACE 视频工作室流程
- `./run.sh test` 命令：一键运行后端测试，交互菜单也新增测试入口
- 自定义端口：支持通过 `./run.sh port backend 9000` / `./run.sh port frontend 3001` 自定义服务端口，持久化到 `.miemie.conf`，也支持环境变量 `MIEMIE_BACKEND_PORT` / `MIEMIE_FRONTEND_PORT` 覆盖

- 视频工作室：接入 HappyHorse 1.0 文生/图生视频
  - 新增 `happyhorse-1.0-t2v`（文生视频）与 `happyhorse-1.0-i2v`（图生视频）两个可选模型
  - 采用独立 `provider=happyhorse`，设置页可单独选择 HappyHorse 使用测试 Key 或生产 Key
  - capability schema 新增 HappyHorse 结构化帮助、参数约束与开发者模式 payload 支持
- 视频工作室：按新版官方文档扩展 HappyHorse 系列
  - 新增 `happyhorse-1.0-r2v`（参考生视频）与 `happyhorse-1.0-video-edit`（视频编辑）两个可选模型
  - `happyhorse-1.0-r2v` 映射到现有 `reference_to_video`，仅支持 1-9 张参考图
  - `happyhorse-1.0-video-edit` 映射到现有 `video_edit_global`，支持 1 个输入视频与 0-5 张参考图
  - 4 个 HappyHorse 模型继续通过 `provider=happyhorse` 复用 DashScope 异步提交、轮询、OSS 与开发者模式链路
- 图片工作室：接入火山引擎 Seedream 图片模型
  - 新增 `doubao-seedream-5.0-lite` 与 `doubao-seedream-4.5`，`provider=volcengine`
  - 支持文生图、1-14 张参考图编辑、0-14 张参考图组图生成
  - 5.0 lite 支持 `output_format=jpeg/png` 与 `web_search`
  - 开发者模式展示 Seedream canonical request、厂商 payload、request id、usage、tools、单图错误和 raw response
- 设置页：新增独立“火山引擎 Ark API Key”模块
  - `volcengine_api_key` 独立保存，不复用 DashScope 测试/生产 Key 池
  - 设置接口返回 `volcengine_api_key_masked` 与 `is_volcengine_api_key_set`

### 变更 (Changed)
- 设置页保存交互改为模块化：
  - 移除页面底部“保存所有设置”
  - Key、火山 Key、API 地域、文本模型、OSS 各模块各自保存
  - 通知、文本模型开关和 OSS 启用开关变更后自动保存
- 设置页：Key 路由新增 HappyHorse 独立选择项，并确认 Wan / HappyHorse / Kling / Vidu 均按各自 profile 实际取用测试或生产 Key。
- 视频工作室：更新 HappyHorse 文生/图生视频参数口径，图片格式与媒体限制以新版官方文档和平台 spec 为准。
- 视频工作室：HappyHorse 文生/图生 capability 明确暴露语义化 smoke/full `verification_profiles`，不再只依赖通用默认档位。
- 图片测评导出体验升级：
  - 导出按钮增加 loading 态，避免大报告导出时误判为无响应
  - 图片内嵌下载改为并发执行，并对超时/网络抖动/5xx/429 做多次重试
  - 对 403/404/410 等明显失效 URL 快速回退，减少整体卡顿
- 管理脚本：TUI 中“更新到最新版本”改为默认执行“拉取代码并自动应用到当前运行服务”
- 管理脚本：更新流程会记录更新前实际运行模式，并在重启后校验运行中的 `git_commit / run_mode / serve_frontend`
- 管理脚本：依赖刷新从比较 `HEAD~1` 改为比较“更新前 commit → 更新后 commit”，避免多提交更新时漏装依赖
- 管理脚本：默认运行模式持久化到 `.miemie.conf`，服务器场景长期偏向 `prod`
- 图片测评手动重试范围从仅 `failed` 扩展为 `failed + unsupported`，用于重试因输入图预检暂时失败而标记为 `unsupported` 的单元
- 视频工作室：参数迁移提示只在用户主动切换模型时提示一次，创建/编辑弹窗初始化和切任务类型时不再重复弹出“已保留兼容参数”通知
- 视频工作室：设置页支持两把 DashScope Key（测试/生产），并为 `Wan / Kling / Vidu` 分别指定当前走哪把 Key
- 音频工作室：将"我的音色"和"任务历史"从页面底部独立卡片移至顶部标签页
  - 新增标签页：我的音色（显示数量）、任务历史（显示数量）
  - 与文本转语音、声音复刻、声音设计平级展示，切换更便捷
- 视频工作室：局部编辑任务改为“首帧提取 -> 前端绘制 Mask -> 服务端二值化上传 -> 提交 VACE”的完整流程
- 视频工作室：任务卡片和详情弹窗支持展示源视频首帧、参考图和 Mask 缩略图
- 管理脚本：`./run.sh install`、`./run.sh start --prod` 和维护菜单新增服务器资源检测与推荐逻辑
  - 自动检测内核、CPU、内存和当前 Swap
  - 自动推荐 `MIEMIE_WORKERS` 和 `NODE_BUILD_MEMORY_MB`
  - 用户确认后持久化到 `.miemie.conf`，并在应用后校验是否生效
- 管理脚本：生产模式启动顺序调整为“先构建前端，再启动后端”，降低小内存服务器的资源峰值
- 管理脚本：`./run.sh status` 新增当前 Workers 与 Node 构建内存显示

### 修复 (Fixed)
- 图片工作室：复核 Seedream 5.0 lite / 4.5 文档口径，清晰度档位 schema label 改为纯 `2K/3K/4K`，Seedream 参数面板新增“组图功能”开关；明确 `guidance_scale` 仅 Seedream 3.0 t2i 支持，5.0 lite / 4.5 不展示也不下发。
- 图片工作室：整理 Seedream 尺寸选项来源并参考 Wan2.7 改为互斥尺寸方案，`size` 参数只暴露 2K/3K/4K 清晰度档位，固定像素尺寸通过 `common_sizes` 展示；前端先选择“清晰度档位 / 固定尺寸”二选一，清晰度模式不再展示比例，差异说明收进 popover。
- 设置页：修复空白 Key 更新会覆盖已有火山引擎 Ark API Key，导致 Seedream 生成提示未配置的问题；Key 字段现在会 trim，空白表示不修改。
- 视频工作室：修复 capability 中 `max_reference_videos=0` 被前端默认值覆盖的问题，HappyHorse 参考生视频不再显示参考视频选择控件。
- 视频工作室：厂商在提交阶段直接失败且未返回 `task_id` 时，现在会把 `request_id`、错误码、错误信息和原始响应保存到 `provider_result_meta.submit_error`，开发者模式可直接查看。
- 图片工作室生产环境卡顿治理：
  - 开发者模式未展开时不再自动请求 `/api/studio/preview-payload`
  - payload 预览请求增加取消/去重，减少无效并发
  - `POST /api/studio/{task_id}/generate` 改为先返回 `generating`，再在后台执行 wan2.7 远程参考图探测与最终 payload 构建
  - 任务弹窗“开始生成/重新生成”按钮增加“提交中”即时反馈
  - 同一任务重复点击生成时，前端同步防重入，后端也会对重复 `generate` 请求执行 no-op 去重
- 图片工作室生成结果统一改为“先落本地暂存，再上传 OSS”：
  - 对 DashScope 临时图片链接补齐统一持久化入口，避免临时 URL 直接写入最终任务结果
  - OSS 上传增加多次自动重试；成功后立即删除本地暂存文件
  - 重试耗尽时，对可恢复故障临时回退 `/assets/...` 本地图片，并在前端返回 warning / 本地回退标记
  - 对 `HTTP 403/404`、Bucket/鉴权异常等不可恢复错误不保留本地回退，避免本地存储被滥用
- 图片工作室本地回退图增加补偿重传与清理：
  - 打开任务详情或列表时会懒触发到期图片后台重传 OSS
  - 新增任务级与项目级“一键重传回退图到 OSS”
  - 本地回退文件 7 天后自动标记过期并清理
  - 本地回退图禁止直接保存到图库，避免长期引用服务器本地文件
- `wan2.7` 图片工作室与图片测评在 OSS 转存失败时补充结构化日志，便于区分“代码未生效 / OSS 配置异常 / 服务器下载超时”
- 图片测评 `interactive_edit` 执行链路补齐 wan2.7 的 `bbox_list` 归一化快照，避免预览正确但真实提交时退化成空数组导致整批 `InvalidParameter`
- wan2.7 任务轮询失败时改为优先读取 `output.code / output.message`，测评与工作室可直接展示厂商返回的具体错误原因
- wan2.7 图片输入预检：
  - 支持 `data:image/...;base64,...`
  - 图片下载失败会返回 HTTP 状态、content-type、超时或协议错误
  - 图片解码失败会返回内容类型和字节数
  - 每张输入图预检增加短间隔重试，避免一次网络抖动直接把测评单元标记为 `unsupported`
- 可灵视频编辑：对输入视频时长、帧率和分辨率做前置校验，避免用户提交后才收到厂商侧 `InvalidParameter`
- 视频工作室：创建/编辑能力弹窗仅在打开时挂载，避免隐藏弹窗参与初始化导致重复通知
- 项目删除时补全所有 13 种关联数据（gallery、studio、audio、video_library、text_library、video_studio、audio_studio、voices 等）的级联删除
- Storage 缓存字典（`_storage_cache`）添加 `threading.Lock` 保护，防止多线程重复创建实例
- 所有 JSON 读操作统一使用 `_read_json_with_lock` + `fcntl.LOCK_SH` 共享锁，确保读写一致性
- 前端 Videos/VideoStudio 页面组件卸载时清空 `pollingRef`，防止离开页面后继续发送网络请求
- Studio/Frames/VideoStudio 页面中残余的硬编码十六进制颜色替换为 Ant Design `theme.useToken()` token
- Settings/LLMConfigForm 中 `form.getFieldValue()` 替换为 `Form.useWatch`，确保表单联动即时更新
- `generationStore` 中 `Set` 类型字段明确排除在 Zustand persist 序列化之外
- 5 处静默 `except Exception: pass` 改为 `logger.warning()`，保留降级逻辑但记录日志
- `oss.py` 和 `studio.py` 中约 25 处 `print()` 替换为标准 `logging`
- `UserService` 单例 `get_user_service()` 添加 `threading.Lock` double-checked locking
- `user_service.py` 中 `_save_users()` 和 `_save_sessions()` 改为原子写入
- slowapi 限流装饰器参数名冲突：Pydantic 模型参数从 `request` 重命名为 `data`，避免与 `starlette.requests.Request` 冲突导致 500 错误
- 管理脚本：生产模式默认 worker 数改为更保守的自动推荐，避免 `gunicorn + vite build` 同时启动时把小内存服务器打满
- 管理脚本：Linux 小内存服务器支持在用户确认后自动创建并校验 Swap，减少构建或重启时假死

### 之前的新增 (Added)
- 视频工作室：新增 wan2.6-r2v-flash 参考生视频模型
  - 极速参考生视频，支持有声/无声切换（audio toggle）
  - 支持多镜头叙事（shot_type: single/multi）
  - 720P/1080P 分辨率，2-10秒连续时长
  - 支持参考视频（最多3个）和参考图片（最多5张）
- 视频工作室：新增 wan2.6-t2v 文生视频模型
  - 支持多镜头叙事、自动配音/自定义音频
  - 720P/1080P 分辨率，2-15秒连续时长
  - 支持负面提示词、智能改写、水印、随机种子

### 变更 (Changed)
- 视频工作室：wan2.6-t2v 时长从固定选项 [5,10,15] 改为连续范围 [2,15]（对齐 API 文档）
- 视频工作室：wan2.6-i2v 时长从固定选项 [5,10,15] 改为连续范围 [2,15]（对齐 API 文档）
- 视频工作室：wan2.6-r2v audio 改为由参考视频自动决定，不再支持手动 toggle
- 视频工作室：参考生视频默认模型从 wan2.6-r2v 改为 wan2.6-r2v-flash
- 前端文生视频 tab 时长控件支持 duration_range 连续输入（InputNumber）
- 前端参考生视频 tab 支持动态切换模型，根据模型能力显隐 audio toggle

- 视频工作室：接入万相2.2数字人模型（wan2.2-s2v）
  - 基于单张图片和音频生成口型同步的说话/唱歌/表演视频
  - 支持真人（肖像、半身、全身）及卡通人物
  - 支持 480P/720P 分辨率，默认 720P
  - 音频从音频库选取，图片从图库选取
  - 新建 `digital_human.py` 服务及 `wan22_s2v.py` 模型注册
  - VideoStudioPage 按模型能力动态显隐控件
- 图片工作室：接入千问图像 2.0 系列模型（qwen-image-2.0-pro / qwen-image-2.0）
  - 双模式：无参考图为文生图，有参考图（1-3张）为图像编辑
  - 单次请求支持输出 1-6 张图片（n 参数）
  - 自由尺寸设定，总像素 512×512 至 2048×2048
  - 支持负面提示词、智能改写、水印、随机种子
  - 新建 `qwen_image_2.py` 模型服务及注册
  - StudioPage 新增专属参数面板及验证逻辑
- 音频工作室：CosyVoice (cosyvoice-v3-flash) 文本转语音功能
  - 60+ 系统音色（社交、儿童、方言、海外、客服、助手等分类）
  - 支持音量/语速/音高/种子/格式/语言提示/SSML/Instruct 等参数
  - 生成音频自动上传 OSS，可保存至音频库
- 音频工作室：声音复刻功能
  - 从音频库选择 10~20 秒音频样本创建自定义音色
  - 后台自动轮询审核状态，审核通过后可用于 TTS
- 音频工作室：声音设计功能
  - 通过文本描述生成自定义音色，返回预览音频
  - 支持采样率和格式设置
- 音色管理：我的音色列表，支持试听和删除
- 后端新增 `AudioStudioTask` 和 `VoiceProfile` 数据模型
- 后端新增 `CosyVoiceTTSService`、`CosyVoiceCloneService`、`CosyVoiceDesignService`
- 后端新增 `/api/audio-studio` 路由（TTS/复刻/设计/音色管理）
- Storage 新增 `audio_studio` 和 `voices` 目录与 CRUD 方法
- 前端 `audioStudioApi` 接口和 TypeScript 类型定义
- 前端 AudioStudioPage 三 Tab 页面完整实现

- 后台异步生成：图片工作室 `/generate` 端点通过 `asyncio.create_task()` 后台执行，立即返回
- 前端轮询模式：StudioPage 参照 VideoStudioPage 实现 polling，支持多任务并发生成
- 生产部署支持：`./run.sh start --prod` 启动 gunicorn 多 worker + 前端构建
- API 限流：slowapi 全局限流（200 请求/分钟/IP）
- 自动更新机制：`./run.sh auto-update enable` 每日自动拉取更新，含数据备份
- 版本回滚：`./run.sh rollback` 支持回滚到上一个版本
- 双主题系统：日间模式（蓝白色系）和夜间模式（灰金色系）
- 侧边栏主题切换按钮（用户名右侧，太阳/月亮图标）
- `themeStore.ts`：主题状态管理（Zustand + localStorage 持久化）
- `theme/index.ts`：集中管理双主题 ThemeConfig 定义
- `docs/UI_GUIDELINES.md`：UI 设计规范文档
- 登录页双主题适配（不同渐变背景、毛玻璃效果）

### 变更 (Changed)
- 图片工作室从同步阻塞改为后台异步 + 前端轮询，UI 不再阻塞
- HTTP 客户端统一为 httpx，移除 requests 和 aiohttp 依赖
- DashScope SDK 同步调用包装为 `asyncio.to_thread()`，避免阻塞事件循环
- 会话验证改为每次从文件读取，支持多 worker 部署
- 全站 22 个页面 + 5 个通用组件使用 `theme.useToken()` 替代硬编码颜色
- 统一 CSS 变量系统：移除 `--studio-*` 和 `--color-*` 两套旧变量，改由 Ant Design token 驱动
- 清理 Tailwind 配置：移除硬编码 studio 颜色
- 更新 `main.tsx`：ConfigProvider 根据主题状态动态切换算法
- 创建开发文档目录 (`docs/`)

### 修复 (Fixed)
- 图片生成任务不再阻塞 UI，可同时创建多个任务
- StorageService 所有保存方法统一使用文件锁，确保并发安全
- 批量生成重置时同时清空 `generatingItems` 状态

---

## [1.0.0] - 2025-12-30

### 新增 (Added)

#### 核心功能
- 多用户支持：用户注册、登录、数据隔离
- 项目管理：创建、编辑、删除项目
- 分镜脚本：AI 生成/优化、手动编辑、多版本对比
- 角色/场景/道具管理：从脚本提取、图片生成、多版本选择
- 分镜首帧生成：基于分镜自动生成首帧图
- 视频生成：首帧转视频、批量生成

#### 工作室
- 图片工作室：灵活的图片生成任务管理
- 视频工作室：文生视频、图生视频、参考生视频、首尾帧生视频任务管理

#### 媒体库
- 图库：图片上传、URL 导入、分类管理
- 音频库：音频上传管理
- 视频库：视频上传管理
- 文本库：文本片段管理

#### 模型支持
- 文生图：wan2.6-t2i, wan2.5-t2i-preview, wan2.6-image
- 图生图：wan2.5-i2i-preview, qwen-image-edit-plus
- 图生视频：wan2.5-i2v-preview, wan2.6-i2v-preview, wanx2.1-i2v-preview
- 视频生视频：wan2.6-r2v
- LLM：qwen3-max, qwen-plus-latest

#### 集成
- 阿里云 OSS 图片/视频持久化存储
- DashScope API 集成（文生图、图生视频、LLM）

### 变更 (Changed)
- 平台名称从 "AI 视频工作室" 改为 "MieMie-Studio"
- 模型显示名称标准化为 "x生x <model code>" 格式

### 修复 (Fixed)
- OSS 测试连接误报权限错误
- 批量生成首帧按钮不响应
- wan2.6-r2v 前端只能选择 2 个参考视频（已改为 3 个）
- 图片工作室文生图任务无法设置输出尺寸

---

## 版本规范

### 版本号格式

`MAJOR.MINOR.PATCH`

- MAJOR: 不兼容的 API 变更
- MINOR: 向后兼容的新功能
- PATCH: 向后兼容的 Bug 修复

### 变更类型

- **Added**: 新功能
- **Changed**: 现有功能变更
- **Deprecated**: 即将移除的功能
- **Removed**: 已移除的功能
- **Fixed**: Bug 修复
- **Security**: 安全相关修复

### 示例条目

```markdown
## [1.1.0] - 2025-01-15

### Added
- 新增 xxx 功能 (#issue-number)
- 支持 xxx 模型

### Changed
- 优化 xxx 性能
- 调整 xxx 默认值

### Fixed
- 修复 xxx 问题 (#issue-number)
```

---

*请在每次发布时更新此文档。*
# 2026-04-01

## 视频工作室稳定化
- 对齐 `Wan / Kling / Vidu` 本地视频文档中的参数、条件逻辑、互斥规则与尺寸/分辨率关系
- 统一视频工作室默认值：`watermark=false`，支持布尔 `audio` 的模型默认 `audio=true`
- 移除视频工作室中的推荐标签与推荐状态展示
- 新增 `POST /api/video-studio/preview-payload`，支持预览 canonical 请求与厂商请求体
- 新建任务弹窗和任务详情新增默认折叠的“开发者模式”
- 任务成功后自动抽取输出视频首帧缩略图并保存到 `thumbnail_url`
- 新增视频任务完成浏览器通知和设置项 `video_task_notifications_enabled`
- 参数帮助统一使用 Popover，补充了含义、限制、选择建议、示例和依赖关系说明
# 2026-04-01

## 图片工作室

- 接入 `wan2.7-image-pro` 与 `wan2.7-image`
- 图片工作室新增能力化任务类型：文生图、图像编辑、交互式编辑、组图生成
- 新增 `wan2.7` 的尺寸模式、交互式框选、颜色主题、组图模式与开发者模式
- 图片工作室开发者模式支持查看 canonical 请求体、厂商 payload、task_ids、request_ids、provider_result_meta
- 图片工作室新增任务完成浏览器通知，页面失焦时继续轮询
- 修复 `/studio/models/available` 被旧配置覆盖导致 registry 参数帮助丢失的问题
- 接入 `wan2.7-i2v` 与 `wan2.7-videoedit` 到视频工作室
- 新增视频任务类型 `video_extension`（视频续写），支持 `first_clip + optional last_frame`
- `wan2.7-videoedit` 接入现有“视频编辑”，支持 `ratio`、`audio_setting`、0-3 张参考图
- 视频工作室能力 schema、开发者模式、任务详情与回归测试已同步支持 `wan2.7` 视频模型
