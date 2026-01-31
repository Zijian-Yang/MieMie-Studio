# MieMie-Studio

基于阿里云通义万相 API 的 AI 漫剧/短剧视频生成平台，支持从剧本创作到视频生成的完整工作流程。

## 功能特性

- **分镜脚本**：支持剧本输入、AI 编剧优化、多模型对比、流式输出
- **角色管理**：从剧本自动提取角色、生成角色三视图、音色配置（开发中）
- **场景管理**：自动提取场景、生成场景空镜图
- **道具管理**：提取重要道具、生成道具图片
- **分镜首帧**：根据分镜脚本生成首帧图
- **视频生成**：使用首帧图生成视频片段

## 技术栈

### 前端

- React 18 + TypeScript
- Ant Design 5.x (深色主题)
- Zustand 状态管理
- Vite 构建工具
- TailwindCSS

### 后端

- Python FastAPI
- 阿里云 DashScope SDK
- JSON 文件存储

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.10+
- 阿里云百炼 API Key

### 一键启动（推荐）

```bash
# 首次运行会自动安装依赖、创建虚拟环境
./run.sh start

# 查看服务状态
./run.sh status

# 停止服务
./run.sh stop

# 重启服务
./run.sh restart

# 查看更多命令
./run.sh help
```

### 手动安装和启动

```bash
# 安装依赖
./run.sh install

# 或手动安装：
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install

# 手动启动后端 (端口 8000)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 手动启动前端 (端口 3000，另一个终端)
cd frontend
npm run dev -- --host
```

### 配置 API Key

1. **后端配置**（可选）：复制 `backend/data/config.example.json` 为 `backend/data/config.json`，填入 DashScope API Key 与（若使用 OSS）阿里云 OSS 凭证。不复制则可通过前端设置页配置 API Key。
2. 打开浏览器访问 http://localhost:3000，点击左侧菜单「设置」输入百炼 DashScope API Key。

**注意**：请勿将含真实密钥的配置文件提交到仓库。

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
├── docs/                       # 开发文档
├── requirements.txt            # Python 依赖
├── run.sh                      # 启动管理脚本
└── README.md
```

## 工作流程

1. **创建项目**：在项目列表页创建新项目
2. **编写剧本**：输入或上传剧本，可选使用 AI 编剧优化
3. **提取角色**：从剧本自动提取角色，生成角色图片
4. **提取场景**：自动提取场景，生成场景空镜
5. **提取道具**：提取重要道具，生成道具图片
6. **生成首帧**：根据分镜脚本生成每个镜头的首帧图
7. **生成视频**：使用首帧图生成视频片段

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整 API 文档。

## 使用的阿里云 API

- [文生图 API](https://www.alibabacloud.com/help/zh/model-studio/text-to-image-v2-api-reference)
- [图生视频 API](https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference)
- [通义千问 API](https://www.alibabacloud.com/help/zh/model-studio/developer-reference/use-qwen-by-calling-api)

## License

MIT
