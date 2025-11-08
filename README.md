# FFmpeg UI

[![Vue 3](https://img.shields.io/badge/Vue.js-3-42b883)](https://vuejs.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.118-009688)](https://fastapi.tiangolo.com/) [![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6)](https://www.typescriptlang.org/)

本项目是一个基于 Web 的 FFmpeg 可视化操作界面，旨在提供一个现代、易用、响应式的界面来执行常见的音视频处理任务。它采用前后端分离架构，并支持打包为原生安卓应用。

## ✨ 功能特性

-   **用户认证**: 安全的注册和登录系统。
-   **文件管理**: 支持拖拽上传、文件列表管理和下载。
-   **参数化处理**: 提供丰富的选项来定制 FFmpeg 命令，如裁剪、编解码器选择、比特率、分辨率调整等。
-   **实时任务监控**: 通过 WebSocket 实时更新处理进度，支持多任务排队。
-   **任务历史**: 查看已完成或失败的任务，并获取详细日志。
-   **跨平台支持**: Web 端应用，并可通过 Capacitor 打包为安卓原生应用。

## 🚀 技术栈

#### 前端 (Frontend)

-   [Vue 3](https://vuejs.org/) (使用组合式 API)
-   [Vite](https://vitejs.dev/)
-   [TypeScript](https://www.typescriptlang.org/)
-   [Pinia](https://pinia.vuejs.org/) (状态管理)
-   [Ant Design Vue](https://www.antdv.com/) (UI 组件库)
-   [Capacitor](https://capacitorjs.com/) (原生应用打包)

#### 后端 (Backend)

-   [Python 3.11+](https://www.python.org/)
-   [FastAPI](https://fastapi.tiangolo.com/)
-   [SQLAlchemy](https://www.sqlalchemy.org/) (ORM)
-   [Pydantic](https://docs.pydantic.dev/) (数据验证)
-   [SlowAPI](https://github.com/laurents/slowapi) (API 速率限制)
-   [Uvicorn](https://www.uvicorn.org/) & [uv](https://github.com/astral-sh/uv)

## 📂 项目结构

```
.
├── backend/         # Python FastAPI 后端应用
├── frontend/        # Vue 3 Vite 前端应用
└── run.py           # 后端启动脚本
```

## 🛠️ 本地开发设置

在开始之前，请确保您的系统已安装 [Node.js](https://nodejs.org/) (v18+), [Python](https://www.python.org/) (3.11+) 和 [FFmpeg](https://ffmpeg.org/download.html)。

#### 1. 克隆仓库

```bash
git clone <your-repository-url>
cd ffmpeg_UI
```

#### 2. 后端设置

```bash
# 进入后端目录
cd backend

# (推荐) 使用 uv 创建并激活虚拟环境
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装 Python 依赖
uv pip install -e .

# 配置环境变量
# 在 backend/ 目录下创建一个 .env 文件，并填入以下内容
# 注意：这个文件也可能在项目根目录，取决于你的 dotenv 配置
```

**`.env` 文件模板:**

请在项目根目录创建一个 `.env` 文件，内容如下：

```env
# --- 前端配置 (Vite 和 Capacitor 会读取) ---
VITE_API_BASE_URL=http://127.0.0.1:8000

# --- 后端配置 (FastAPI 会读取) ---
# 逗号分隔，不要有空格
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

#### 3. 前端设置

```bash
# 进入前端目录
cd frontend

# 安装 Node.js 依赖
npm install
```

#### 4. 启动项目

您需要**打开两个终端**来分别启动后端和前端。

-   **终端 1：启动后端服务** (在项目根目录下)
    ```bash
    uv run -- python run.py
    ```
    您应该会看到 Uvicorn 在 `http://127.0.0.1:8000` 上运行。

-   **终端 2：启动前端开发服务器** (在 `frontend/` 目录下)
    ```bash
    npm run dev
    ```
    现在，您可以在浏览器中打开 `http://localhost:5173` 来访问应用。

## 📦 生产构建

#### 前端

```bash
# 在 frontend/ 目录下运行
npm run build
```
编译后的静态文件将位于 `frontend/dist/` 目录。

## 📱 打包安卓应用

1.  **构建前端静态文件**:
    ```bash
    # 在 frontend/ 目录下运行
    npm run build
    ```

2.  **添加并同步 Android 平台** (首次运行时需要 `add`):
    ```bash
    # 在 frontend/ 目录下运行
    npx cap add android
    npx cap sync android
    ```

3.  **使用 Android Studio 打开并构建**:
    -   打开 Android Studio。
    -   选择 "Open an existing project"。
    -   导航并选择项目的 `frontend/android` 目录。
    -   等待 Gradle 同步完成后，通过菜单 "Build" -> "Build Bundle(s) / APK(s)" -> "Build APK(s)" 来生成 APK 文件。

## 📜 可用脚本 (前端)

在 `frontend/` 目录下：

-   `npm run dev`: 启动开发服务器。
-   `npm run build`: 为生产环境构建应用。
-   `npm run lint`: 使用 ESLint 检查代码。

## 💡 推荐的 IDE 设置

-   [VSCode](https://code.visualstudio.com/)
-   [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (官方 Vue 插件)
-   [Python (Microsoft)](https://marketplace.visualstudio.com/items?itemName=ms-python.python) (官方 Python 插件)