# 开源合规检查清单

本文档基于「极简开源指南」对仓库进行自检，便于在正式提交流程前补齐合规项。**流程发起人需在提交前逐项确认并完成“必须由你完成”的动作。**

---

## 一、敏感数据与 YY 扫描类（需自行排查确认）

### 1. 已发现并处理的问题

| 类型 | 路径 | 说明 | 处理情况 |
|------|------|------|----------|
| **API Key / 密钥** | `backend/data/config.json` | 含 DashScope API Key、OSS access_key_id/secret、bucket 名 | 已在 `backend/.gitignore` 中忽略，**不会随本次提交进入仓库**。若历史上曾提交过，需从历史中清除并更换密钥。 |
| **API Key** | `text_to_image_config.json` | 根目录脚本用配置，含真实 API Key | 已加入根目录 `.gitignore`，并新增 `text_to_image_config.example.json` 供参考，**真实配置不得提交**。 |
| **用户与会话数据** | `backend/data/users.json` | 明文密码、用户名、展示名、时间戳等 | 已加入 `backend/.gitignore` 与根目录 `.gitignore`。若此前已提交，**必须从 Git 历史中删除并视为泄漏，修改所有相关密码。** |
| **会话数据** | `backend/data/sessions.json` | token → user_id 映射 | 同上，已忽略；若曾提交需从历史中清除。 |
| **用户使用数据** | `backend/data/users/` | 各用户目录下的 config、项目、角色、场景、分镜、视频等使用产生的内容 | 已加入根目录及 `backend/.gitignore`（`data/users/`），不纳入版本库、不推远端。 |

**说明：** 代码中对 API Key、OSS 密钥、用户密码的引用均为“从配置/环境读取”或“请求参数”，未在源码中硬编码具体密钥字符串，符合“不提交敏感信息”的实践。

### 2. 漏洞「Aliyun_AK_Check / sensitive_AK_leak」说明（紧急）

**问题位置：Git 历史提交，不是当前工作区。**

扫描报出的路径形如：  
`<commit>@backend/data/users/<user_id>/config.json#L1`  
（例如 `313e7e84...@backend/data/users/bd589dd2-.../config.json`、`c77463cc...@backend/data/users/12afc526-.../config.json`）

- **根因**：多用户功能加入后，曾把**用户目录下的 config.json**（内含 OSS `access_key_id` / `access_key_secret`）提交进了仓库。虽然后来已将 `backend/data/users/` 加入 `.gitignore` 并停止跟踪，但这些文件仍然存在于**历史提交**中，扫描工具会扫历史，因此仍报「阿里云 AK 泄露」。
- **涉及历史**：至少包括提交 `0b838e4`（新增多用户系统）及之后若干提交中对 `backend/data/users/*/config.json` 的提交。
- **必须修复**：从**整段 Git 历史**中删除 `backend/data/users/` 下所有文件并强制推送；并在阿里云控制台**立即禁用/轮换**已泄露的 AK（`LTAI5tGbwT6y6vYhwUkEJRg6`、`LTAI5tQTP3AWmE48cqSyXtbJ` 等），因为历史若曾推送到远端则视为已泄露。

**从历史中彻底删除 `backend/data/users/` 的步骤**（在仓库根目录执行）：

```bash
# 1. 安装 git-filter-repo（若未安装）：pip install git-filter-repo

# 2. 备份当前分支并拉取最新
git fetch origin
git branch backup-before-filter  # 可选：保留备份分支

# 3. 从全部历史中删除 backend/data/users/ 目录
git filter-repo --path backend/data/users/ --invert-paths --force

# 4. 推送重写后的历史（会改写远端历史，需协调协作者）
git push origin --force --all
git push origin --force --tags   # 若有 tags
```

若使用 **BFG** 代替（需先 `git rm -r --cached backend/data/users/` 并提交一次，再跑 BFG 删历史中的大文件/目录），或使用 `git filter-branch`，同样需确保 `backend/data/users/` 在所有提交中被删除，然后 force push。完成后**必须**在阿里云控制台轮换/禁用上述 AK。

### 3. 你必须完成的操作（开源前）

1. **从 Git 历史中彻底删除敏感路径（见上方「Aliyun_AK_Check」修复步骤）：**
   - **必须删除**：`backend/data/users/`（用户目录下的 config.json 等，含 OSS AK）
   - 若也曾提交过：`backend/data/users.json`、`backend/data/sessions.json`、`text_to_image_config.json`  
   使用 `git filter-repo` 或 BFG 从历史中一并删除，并**轮换所有已暴露的 API Key、OSS 密钥和用户密码**。
2. **本地/内网数据清理：**  
   `backend/data/users.json` 中曾出现明文密码与不当账号内容，仅适合本地开发。开源前请确认：
   - 生产/对外环境中从未使用该文件内容；
   - 所有测试账号与密码已在需要的地方修改或废弃。
3. **YY 扫描：** 流程要求使用 YY 扫描工具对仓库做敏感数据扫描，扫描完成后**由发起人自行排查确认**所有提示项，本清单不能替代该步骤。

### 4. 可选加固建议

- 用户密码建议改为仅存储哈希（如 bcrypt），避免明文持久化（参见 `backend/app/models/user.py` 注释及 `user_service` 实现）。
- 若开放注册，建议在生产环境使用环境变量或独立密钥管理服务注入 DashScope / OSS 等密钥，而不是仅依赖 `config.json`。

---

## 二、许可证与清源合规

### 1. 项目许可证

- README 中已声明 **MIT**。
- 仓库中已添加 **LICENSE** 文件（MIT）。  
- **你需要做的：** 在 `LICENSE` 中把 `Copyright (c) 2025` 补全为版权方（公司或个人），例如：`Copyright (c) 2025 公司名`。

### 2. 第三方依赖与兼容性

- **后端 (Python)：** 见 `backend/requirements.txt`。主要依赖包括 FastAPI、uvicorn、pydantic、dashscope、oss2、aiohttp、requests、httpx、Pillow、opencv-python-headless 等，均为常见开源组件，MIT/Apache/BSD 等宽松许可证为主。
- **前端 (Node)：** 见 `frontend/package.json`。React、Ant Design、Zustand、Vite、Tailwind 等，均为 MIT 或兼容许可证。
- **建议：** 在流程中按要求运行**清源 SCA**，确认所有开源组件及其许可证与项目所选 MIT 兼容，并保留审查结果备查。

---

## 三、配置与示例文件

- 已提供：
  - `backend/data/config.example.json`：应用所需配置结构示例，无真实密钥。
  - `text_to_image_config.example.json`：根目录文生图脚本配置示例。
- 使用说明可在 README「配置 API Key」等小节中引用以上示例文件，并注明：**请复制为 `config.json` / `text_to_image_config.json` 后填入自己的密钥，勿将真实配置提交到仓库。**

---

## 四、品牌、命名与出口管制（流程侧）

以下由审批节点在流程中确认，本仓库仅做自检提醒：

- **项目名称：** 若为战略/重点开源项目，需按指南完成名称自检（搜索引擎、GitHub、商标、域名等）并与品牌法务确认。
- **出口管制：** 由出口管制审查节点判断是否在出口管制技术清单内，并按规范报备。
- **专利/域名/官网：** 按流程与专利法务、域名法务等对接，如需官网或商标再单独申请。

---

## 五、自检汇总

| 类别 | 状态 | 备注 |
|------|------|------|
| 敏感数据（API Key/密钥） | 已通过 .gitignore 与示例配置规避；历史需人工排查 | 必须从历史中删除曾提交的敏感文件并轮换密钥 |
| 用户/会话数据 | 已加入 .gitignore | 若曾提交须从历史清除并改密 |
| 项目许可证 | 已设 MIT + LICENSE 文件 | 需补全版权方 |
| 第三方许可证 | 待清源 SCA 结果 | 流程中运行清源 SCA |
| 示例配置 | 已提供 | 文档中可引用 |

**最后提醒：** 在发起开源流程前，请务必：  
1）使用 YY 扫描并自行确认；  
2）处理 Git 历史中的敏感文件并轮换所有已暴露密钥；  
3）在 LICENSE 中填写版权方；  
4）与团队及技术一号位对焦项目定位与 1–3 年目标（见极简开源指南）。
