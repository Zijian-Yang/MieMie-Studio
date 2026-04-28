# 工作室模型接入范式指南

> 适用于图片工作室、视频工作室，以及未来继续扩展的音频工作室。
> 这份文档不替代各具体 API 文档，而是沉淀“我们在平台里如何稳定接入一个新模型”的统一方法论。

---

## 一、这份指南解决什么问题

项目早期接入模型时，更偏向：
- 在 `config.py` 增加模型配置
- 在路由里补参数
- 在页面里按模型名写分支

这条路在模型少、能力简单时可行，但随着 `Wan / Kling / Vidu / Qwen` 的能力越来越多，会很快遇到问题：
- 同一个模型支持多个任务能力
- 同一种能力在不同厂商下参数完全不同
- 页面里 if/else 爆炸，难以维护
- 帮助文案、校验规则、默认值和真实 payload 容易漂移

现在我们已经逐步沉淀出更稳定的范式：
- **能力优先，模型次选**
- **canonical request + provider payload**
- **schema 驱动前端**
- **adapter 驱动后端**
- **开发者模式可观测**
- **前后端双层校验**

这份文档就是把这套经验正式写清楚。

---

## 二、核心原则

### 1. 能力优先，模型次选

用户要做的是“图生视频”“视频编辑”“组图生成”，不是“先选某个模型名”。

因此工作室的主入口应该先按 `task_kind` 或能力分类：
- 图片：文生图、图像编辑、交互式编辑、组图生成
- 视频：文生视频、图生视频、首尾帧生视频、参考生视频、视频编辑、局部编辑、视频重绘、视频续写

模型只是某个能力下的可选实现。

### 2. canonical request 是平台统一语义

前端不要直接拼厂商请求体。

正确顺序：
1. 前端组装平台统一语义的 `canonical request`
2. 后端 adapter 根据 `provider + model_id + task_kind` 映射成厂商 payload
3. 开发者模式同时展示两者，便于核对

统一语义的价值：
- 让前端不必理解每个厂商的底层字段细节
- 让编辑、重跑、详情展示能复用同一套数据结构
- 让预览和真实提交使用同一套 builder，降低漂移风险

### 3. schema 驱动前端，页面不硬编码模型差异

参数显隐、限制、帮助文案、素材位说明，优先来自 schema：
- 视频工作室：`/api/video-studio/capabilities`
- 图片工作室：`/api/studio/models/available` + `preview-payload`

页面负责：
- 渲染
- 表单交互
- 用户体验

页面不应该重新发明：
- 参数含义
- 选项差异
- 限制规则
- payload 结构

### 4. adapter 驱动后端

后端路由不直接理解所有厂商的所有参数差异。

统一做法：
- 路由接收 canonical request
- adapter 负责：
  - `validate`
  - `build_payload`
  - `submit`
  - `fetch`
  - `normalize_result`

这样新增模型时，只需要在对应能力的 schema 和 adapter 中补齐，不会把复杂度继续堆到 router 里。

### 5. 帮助文案必须结构化

参数帮助不能是零散的一句字符串。

推荐结构：
- `summary`
- `meaning`
- `limits`
- `how_to_choose`
- `examples`
- `notes`

前端统一用 **Popover** 渲染，避免 Tooltip 承载过长内容。

### 6. 校验要分两层

#### 前端校验
- 防呆
- 及时提示
- 禁用明显非法组合

#### 后端校验
- 作为最终权威
- 即使前端漏掉，也必须拦截
- 包括：
  - 参数取值
  - 条件依赖
  - 互斥关系
  - 素材元数据限制
  - 数量上限

### 7. 结果必须长期保存到 OSS

外部模型厂商返回的 URL 往往是临时链接，不能作为平台长期依赖。

统一要求：
- 图片、视频、音频成功后立即转存 OSS
- 任务详情保存：
  - `provider_payload_snapshot`
  - `provider_result_meta`
  - `task_ids`
  - `request_ids`

---

## 三、关键术语

### `task_kind`
平台级任务能力，例如：
- `text_to_image`
- `interactive_edit`
- `image_to_video`
- `video_edit_global`
- `video_edit_local`
- `video_extension`

### `input_assets`
统一素材角色，不直接使用厂商字段名，例如：
- `images`
- `first_frame`
- `last_frame`
- `first_clip`
- `base_video`
- `reference_image`
- `audio`

### `normalized_params`
平台级规范化参数，不直接等于厂商参数名。

### `provider_payload_snapshot`
任务实际发往厂商的请求体快照。

### `provider_result_meta`
厂商返回的任务状态、错误码、请求 ID、usage 等元数据。

---

## 四、标准接入流程

### 第 1 步：先读官方文档，不先写代码

先整理清楚：
- 模型支持哪些能力
- 每个能力需要哪些素材位
- 参数有哪些
- 哪些参数有条件显示/条件生效
- 哪些参数互斥
- 尺寸/分辨率怎么定义
- 结果 URL 有效期多久

不要在没搞清任务语义前就先堆前端控件。

### 第 2 步：把模型映射到平台能力

问自己两个问题：
1. 这个模型应该复用现有任务能力，还是需要新增一个 `task_kind`？
2. 它是“新模型”，还是“新能力”？

例如：
- `wan2.7-videoedit` 应该归入现有 `video_edit_global`
- `wan2.7-i2v` 支持 `image_to_video`、`keyframe_to_video`，但还新增了 `video_extension`
- `wan2.7-i2v-2026-04-25` 这类带日期快照模型应作为独立模型接入，不能默认当成主线模型别名；除非 spec 明确要求，否则也不替换现有默认模型

### 第 3 步：先写 schema，再写前端

优先补齐：
- 支持的 `task_kind`
- 输入素材角色
- 参数 schema
- 结构化帮助
- 条件逻辑
- UI hints

如果 schema 还没稳定，不要急着做页面交互。

### 第 4 步：先做 preview，再做 submit

新增模型时，先把 `preview-payload` 打通。

原因：
- 可以验证 canonical request 是否正确
- 可以验证 provider payload 是否与文档一致
- 能提前发现字段丢失、顺序错误、默认值错误等问题

### 第 5 步：让开发者模式可见

所有工作室新任务和任务详情都应该能看到：
- canonical request
- provider payload
- task id / request id
- provider result meta

没有这层可观测性，多模型接入会非常难排查。

### 第 6 步：最后补测试

至少覆盖：
- 参数显隐
- 条件逻辑
- payload 映射
- 非法组合拦截
- 成功结果落 OSS
- 任务详情元信息保留

---

## 五、前端设计规则

### 1. 任务页面保持稳定骨架

推荐拆成三层：
- 任务通用区
- 模型能力区
- 模型专属高级区

这样用户切模型时不会觉得“整页换了一套产品”。

### 2. 素材位是第一等公民

素材输入必须按角色设计，而不是按厂商字段设计。

例如视频工作室里：
- `first_frame`
- `last_frame`
- `first_clip`
- `base_video`
- `reference_image`
- `audio`

用户能理解的是素材角色，不是 `media.type=feature`。

### 3. 切模型时只迁移兼容参数

切模型时要有明确规则：
- 兼容值保留
- 不兼容值回退默认值
- 只在用户主动切模型时提示

不要提示的场景：
- 首次打开弹窗
- 切任务类型自动回填默认模型
- 编辑弹窗初次加载

### 4. Popover 要解释“怎么选”，不只是“是什么”

好的帮助说明至少能回答：
- 这个参数控制什么
- 有什么限制
- 什么时候应该选它
- 和哪个参数互斥或依赖
- 一个简短例子

### 5. 开发者模式默认折叠，但必须一直在

它不是调试开关，而是平台级可观测性。

---

## 六、后端实现规则

### 1. router 不负责厂商细节

router 负责：
- 鉴权
- 接收请求
- 加载任务
- 调用 adapter
- 持久化结果

router 不负责：
- 理解所有模型参数
- 拼厂商 payload
- 写复杂模型分支

### 2. preview 和 submit 必须共用 builder

这是硬规则。

如果 preview 和真实提交用两套逻辑，开发者模式就会失真。

### 3. 远程素材校验要尽量前置

特别是：
- 图片尺寸/格式/透明通道
- 视频时长/fps/大小/分辨率
- 音频时长/格式

但不要把“平台能探测到”和“平台必须阻断”混为一谈。像透明 PNG 这类存在厂商侧容错空间的输入，可以保留探测信息但不前置拦截，再把厂商错误完整回传给用户和开发者模式。

### 4. provider 元信息不要在轮询时洗掉

提交时拿到的：
- `request_id`
- `submitted_at`
- `raw_output`

后续轮询更新时要做“合并保留”，不能把已有字段覆盖成空。

对失败路径同样适用：提交失败、轮询失败、厂商返回 FAILED/CANCELLED，都要尽量保留 `request_id / error_code / error_message / raw_output`。

---

## 七、什么时候还用 `config.py`

`config.py` 仍然有价值，但角色已经变化了。

更适合放在里面的是：
- 全局配置
- 旧页面仍在使用的配置
- 兼容层模型集合
- 非工作室类的简单模型开关

对于图片/视频工作室这种复杂能力页面，更推荐：
- schema
- adapter
- preview-payload
- 开发者模式

也就是说，不是彻底废弃 `config.py`，而是不要再把它当成复杂工作室模型的唯一接入入口。

---

## 八、新模型接入 Checklist

### 文档分析
- [ ] 官方文档已完整阅读
- [ ] 任务能力已映射到 `task_kind`
- [ ] 素材角色已映射到 `input_assets`
- [ ] 参数、默认值、限制、互斥关系已整理

### 后端
- [ ] schema 已补齐
- [ ] adapter 已实现
- [ ] preview-payload 已打通
- [ ] 远程素材校验已补齐
- [ ] 结果转存 OSS 已确认
- [ ] `provider_result_meta` 已完整保留

### 前端
- [ ] 参数显隐正确
- [ ] 条件逻辑正确
- [ ] Popover 帮助完整
- [ ] 开发者模式可见
- [ ] 切模型迁移逻辑正常

### 测试
- [ ] payload 映射测试
- [ ] 非法组合拦截测试
- [ ] 关键场景人工联调

### 文档
- [ ] 更新 `README.md`
- [ ] 更新本地 `docs/CHANGELOG.md`
- [ ] 更新对应前后端文档

---

## 九、当前最成熟的范式在哪

截至目前，最成熟的是：
- **视频工作室**
  - `capabilities + task_kind + adapter + preview-payload + 开发者模式`
- **图片工作室**
  - 正在快速向同一范式靠拢，尤其是 `wan2.7` 之后已经明显稳定

建议后续所有新模型，优先沿着这条路线走，而不是回到“页面手写模型分支 + config.py 堆配置”的旧路径。

---

*最后更新: 2026-04-03*
