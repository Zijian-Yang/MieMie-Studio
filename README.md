# MieMie-Studio

基于阿里云通义万相 API 的 AI 漫剧/短剧视频生成平台，支持从剧本创作到视频生成的完整工作流程。

## 功能特性

- **分镜脚本**：支持剧本输入、AI 编剧优化、多模型对比、流式输出
- **角色管理**：从剧本自动提取角色、生成角色三视图
- **场景管理**：自动提取场景、生成场景空镜图
- **道具管理**：提取重要道具、生成道具图片
- **分镜首帧**：根据分镜脚本生成首帧图
- **视频生成**：使用首帧图生成视频片段

## 技术栈

| 前端 | 后端 |
|------|------|
| React 18 + TypeScript | Python FastAPI |
| Ant Design 5.x (深色主题) | 阿里云 DashScope SDK |
| Zustand 状态管理 | JSON 文件存储 |
| Vite 构建工具 | 阿里云 OSS（可选） |

---

## 快速开始

### 第一步：环境准备

**必需环境：**

| 环境 | 版本要求 | 检查命令 |
|------|---------|---------|
| Node.js | 18+ | `node --version` |
| Python | 3.10+ | `python3 --version` |
| Git | 任意 | `git --version` |

**获取 API Key：**

1. 访问 [阿里云百炼控制台](https://bailian.console.aliyun.com/)
2. 开通 DashScope 服务
3. 创建 API Key 并保存

---

### 第二步：下载项目

**方式一：使用 Git 克隆（推荐）**

```bash
# 克隆项目
git clone https://github.com/Zijian-Yang/MieMie-Studio.git

# 进入项目目录
cd MieMie-Studio
```

**方式二：下载 ZIP 压缩包**

1. 访问 https://github.com/Zijian-Yang/MieMie-Studio
2. 点击绿色的 `Code` 按钮
3. 选择 `Download ZIP`
4. 解压后进入目录

---

### 第三步：启动项目

#### 方式一：一键启动（推荐）

```bash
# 添加执行权限（仅首次需要）
chmod +x run.sh

# 启动服务（首次运行会自动安装依赖）
./run.sh start
```

**首次运行会自动完成：**
- ✅ 创建 Python 虚拟环境
- ✅ 安装 Python 依赖
- ✅ 安装前端依赖
- ✅ 启动后端服务
- ✅ 启动前端服务

**启动成功后会显示：**
```
[OK] MieMie-Studio 启动完成!

  后端: http://localhost:8000
  前端: http://localhost:3000
```

#### 方式二：手动启动

```bash
# 1. 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 安装前端依赖
cd frontend
npm install
cd ..

# 4. 启动后端（终端 1）
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. 启动前端（终端 2，新开一个）
cd frontend
npm run dev -- --host
```

---

### 第四步：配置 API Key

1. 打开浏览器访问 http://localhost:3000
2. 点击左侧菜单「设置」
3. 输入你的阿里云百炼 DashScope API Key
4. 点击保存

**可选配置：** 如需配置 OSS 存储，复制 `backend/data/config.example.json` 为 `backend/data/config.json` 并填入 OSS 凭证。

---

## 管理脚本命令

使用 `./run.sh` 管理项目：

### 服务管理

```bash
./run.sh start      # 启动前后端服务
./run.sh stop       # 停止所有服务
./run.sh restart    # 重启所有服务
./run.sh status     # 查看服务状态
```

### 依赖管理

```bash
./run.sh install    # 安装/重新安装依赖
./run.sh update     # 更新项目到最新版本
./run.sh clean      # 清理缓存/重置依赖
```

### 调试工具

```bash
./run.sh logs              # 连接到后端终端查看日志
./run.sh logs backend      # 查看后端日志文件
./run.sh logs frontend     # 查看前端日志文件
./run.sh attach backend    # 连接到后端 screen 会话
./run.sh attach frontend   # 连接到前端 screen 会话
```

### 其他

```bash
./run.sh version    # 显示版本信息
./run.sh help       # 显示帮助信息
```

---

## 更新项目

### 方式一：使用脚本更新（推荐）

```bash
./run.sh update
```

脚本会自动：
- 检测本地是否有未提交的更改
- 暂存本地更改（如有）
- 拉取最新代码
- 自动更新依赖（如有变化）
- 恢复本地更改

### 方式二：手动更新

```bash
# 1. 停止服务
./run.sh stop

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖（如果依赖有变化）
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 4. 重新启动
./run.sh start
```

---

## 卸载/删除项目

### 完全删除

```bash
# 1. 停止所有服务
./run.sh stop

# 2. 退出项目目录
cd ..

# 3. 删除整个项目
rm -rf MieMie-Studio
```

### 仅清理依赖（保留代码）

```bash
# 删除虚拟环境
rm -rf venv

# 删除前端依赖
rm -rf frontend/node_modules

# 删除日志
rm -rf logs
```

---

## 项目结构

```
MieMie-Studio/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── config.py          # 配置管理
│   │   ├── routers/           # API 路由
│   │   ├── services/          # 业务服务
│   │   │   ├── dashscope/     # 阿里云 API 封装
│   │   │   └── storage.py     # 存储服务
│   │   └── models/            # 数据模型
│   └── data/                  # 数据存储
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/        # 通用组件
│   │   ├── pages/             # 页面组件
│   │   ├── services/          # API 服务
│   │   ├── stores/            # 状态管理
│   │   └── styles/            # 样式文件
│   └── package.json
├── requirements.txt            # Python 依赖
├── run.sh                      # 启动管理脚本
├── LICENSE                     # GPL v3 许可证
└── README.md                   # 本文件
```

---

## 使用流程

1. **创建项目**：在项目列表页创建新项目
2. **编写剧本**：输入或上传剧本，可选使用 AI 编剧优化
3. **提取角色**：从剧本自动提取角色，生成角色图片
4. **提取场景**：自动提取场景，生成场景空镜
5. **提取道具**：提取重要道具，生成道具图片
6. **生成首帧**：根据分镜脚本生成每个镜头的首帧图
7. **生成视频**：使用首帧图生成视频片段

---

## 常见问题

### Q: 启动时提示 "command not found: uvicorn"

**原因**：虚拟环境未激活或依赖未安装

**解决方案**：
```bash
# 使用脚本启动（自动处理）
./run.sh start

# 或手动激活虚拟环境
source venv/bin/activate
```

### Q: 前端启动报错 "bad interpreter: Operation not permitted"

**原因**：macOS 安全机制阻止执行

**解决方案**：
```bash
# 删除并重新安装前端依赖
rm -rf frontend/node_modules
cd frontend && npm install
```

### Q: 如何查看后端实时日志？

```bash
# 方式一：连接到 screen 会话
./run.sh attach backend
# 按 Ctrl+A, 然后按 D 退出（服务继续运行）

# 方式二：查看日志文件
./run.sh logs backend
```

### Q: 端口被占用怎么办？

```bash
# 查看占用端口的进程
lsof -i :8000  # 后端
lsof -i :3000  # 前端

# 结束进程
kill -9 <PID>
```

### Q: 如何在后台运行？

脚本默认使用 `screen` 后台运行，关闭终端不会停止服务。

```bash
# 查看正在运行的 screen 会话
screen -ls

# 重新连接到会话
screen -r miemie-studio-backend
```

### Q: Windows 用户如何使用？

Windows 用户请使用手动启动方式，或安装 [Git Bash](https://gitforwindows.org/) / [WSL](https://docs.microsoft.com/en-us/windows/wsl/) 后运行脚本。

---

## 使用的阿里云 API

- [文生图 API](https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference)
- [图生视频 API](https://help.aliyun.com/zh/model-studio/image-to-video-api-reference)
- [通义千问 API](https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api)

---

## License

GPL v3

本项目采用 GPL v3 开源协议：
- ✅ 可以自由使用、修改和分发
- ✅ 可以用于商业目的
- ✅ 但修改后的代码必须同样开源（GPL v3）
- ✅ 必须保留原作者版权声明

详见 [LICENSE](LICENSE) 文件。

---

## 联系方式

- 项目地址：https://github.com/Zijian-Yang/MieMie-Studio
- 问题反馈：https://github.com/Zijian-Yang/MieMie-Studio/issues
- 邮箱：Zijian-Yang@users.noreply.github.com
