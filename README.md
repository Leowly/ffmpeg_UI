# FFmpeg UI

[![Vue 3](https://img.shields.io/badge/Vue.js-3-42b883)](https://vuejs.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.118-009688)](https://fastapi.tiangolo.com/) [![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6)](https://www.typescriptlang.org/)

本项目是一个基于 Web 的 FFmpeg 可视化操作界面，旨在提供一个现代、易用、响应式的界面来执行常见的音视频处理任务。它采用前后端分离架构，并支持打包为原生安卓应用。

## ✨ 功能特性

- **用户认证**: 安全的注册和登录系统。
- **文件管理**: 支持拖拽上传、文件列表管理和下载。
- **参数化处理**: 提供丰富的选项来定制 FFmpeg 命令，如裁剪、编解码器选择、比特率、分辨率调整等。
- **实时任务监控**: 通过 WebSocket 实时更新处理进度，支持多任务排队。
- **任务历史**: 查看已完成或失败的任务，并获取详细日志。
- **跨平台支持**: Web 端应用，并可通过 Capacitor 打包为安卓原生应用。

## 🚀 技术栈

#### 前端 (Frontend)

- [Vue 3](https://vuejs.org/) (使用组合式 API)
- [Vite](https://vitejs.dev/)
- [TypeScript](https://www.typescriptlang.org/)
- [Pinia](https://pinia.vuejs.org/) (状态管理)
- [Ant Design Vue](https://www.antdv.com/) (UI 组件库)
- [Capacitor](https://capacitorjs.com/) (原生应用打包)

#### 后端 (Backend)

- [Python 3.11+](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/) (ORM)
- [Pydantic](https://docs.pydantic.dev/) (数据验证)
- [SlowAPI](https://github.com/laurents/slowapi) (API 速率限制)
- [Uvicorn](https://www.uvicorn.org/) & [uv](https://github.com/astral-sh/uv)

## 📂 项目结构

```
.
├── backend/         # Python FastAPI 后端应用
├── frontend/        # Vue 3 Vite 前端应用
└── run.py           # 后端启动脚本
```

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
    - 打开 Android Studio。
    - 选择 "Open an existing project"。
    - 导航并选择项目的 `frontend/android` 目录。
    - 等待 Gradle 同步完成后，通过菜单 "Build" -> "Build Bundle(s) / APK(s)" -> "Build APK(s)" 来生成 APK 文件。

## 📜 可用脚本 (前端)

在 `frontend/` 目录下：

- `npm run dev`: 启动开发服务器。
- `npm run build`: 为生产环境构建应用。
- `npm run lint`: 使用 ESLint 检查代码。

## 💡 推荐的 IDE 设置

- [VSCode](https://code.visualstudio.com/)
- [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (官方 Vue 插件)
- [Python (Microsoft)](https://marketplace.visualstudio.com/items?itemName=ms-python.python) (官方 Python 插件)
