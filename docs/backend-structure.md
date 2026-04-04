# FFmpeg UI 后端文档

## 项目概述

FastAPI 后端服务，为 FFmpeg 可视化操作界面提供用户认证、文件管理和音视频处理功能。

---

## 目录结构

```
backend/
└── app/
    ├── main.py              # FastAPI 应用入口
    ├── api/                 # API 路由模块
    │   ├── users.py         # 用户认证
    │   ├── files.py         # 文件路由聚合
    │   ├── upload.py        # 文件上传
    │   ├── download.py      # 文件下载/获取
    │   ├── process.py        # FFmpeg 处理
    │   ├── tasks.py         # 任务管理
    │   ├── delete.py        # 文件删除
    │   └── capabilities.py  # 系统能力查询
    ├── models/              # SQLAlchemy 数据库模型
    │   └── models.py        # User, File, ProcessingTask
    ├── schemas/             # Pydantic 数据验证
    │   └── schemas.py       # 请求/响应模型定义
    ├── core/                # 核心工具
    │   ├── config.py        # 配置管理
    │   ├── database.py      # 数据库连接
    │   ├── deps.py          # 依赖注入
    │   ├── limiter.py       # 速率限制
    │   └── security.py      # JWT/密码安全
    ├── crud/                # 数据库 CRUD 操作
    │   └── crud.py          # 用户、文件、任务 CRUD
    └── services/            # 业务逻辑服务
        ├── manager.py       # WebSocket 连接管理
        ├── worker.py        # 后台任务队列
        ├── processing.py    # 任务处理逻辑
        ├── ffmpeg_runner.py # FFmpeg 执行器
        └── hw_accel.py     # 硬件加速检测
```

---

## 数据库模型

### User (用户)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String | 用户名(唯一) |
| hashed_password | String | 密码哈希 |

### File (文件)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| filename | String | 原始文件名 |
| filepath | String | 存储路径(唯一) |
| owner_id | Integer | 所有者ID |
| status | String | 状态: uploaded/processing/completed/failed |

### ProcessingTask (处理任务)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| ffmpeg_command | Text | FFmpeg 命令 |
| source_filename | String | 源文件名 |
| output_path | String | 输出文件路径 |
| progress | Integer | 进度 0-100% |
| status | String | pending/processing/completed/failed |
| details | Text | 日志/错误信息 |
| owner_id | Integer | 所有者ID |
| result_file_id | Integer | 结果文件ID |

---

## API 端点总览

### 用户认证 (Users)

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/token` | 登录获取 JWT Token | 无 |
| POST | `/users/` | 注册新用户 | 无 |
| GET | `/users/me` | 获取当前用户信息 | JWT |
| POST | `/logout` | 登出 | 无 |

### 文件管理 (Files) - 前缀 `/api`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/upload` | 上传文件 | JWT |
| GET | `/api/files` | 获取用户文件列表 | JWT |
| GET | `/api/file-info` | 获取文件详情(ffprobe) | JWT |
| GET | `/api/download-file/{file_id}` | 下载文件 | JWT |
| GET | `/api/download-temp/{file_id}` | 获取临时下载链接 | JWT |
| GET | `/api/temp-download/{token}` | 临时下载(签名验证) | 无 |
| DELETE | `/api/delete-file` | 删除文件 | JWT |
| GET | `/api/capabilities` | 获取系统能力(硬件加速) | JWT |

### 任务处理 (Tasks) - 前缀 `/api`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/process` | 提交处理任务 | JWT |
| GET | `/api/tasks` | 获取任务列表 | JWT |
| GET | `/api/task-status/{taskId}` | 获取任务状态 | JWT |
| DELETE | `/api/tasks/{task_id}` | 删除任务 | JWT |

### WebSocket

| 路径 | 说明 | 认证 |
|------|------|------|
| `/ws/progress/{task_id}` | 实时任务进度推送 | 无(通过 task_id 验证) |

---

## 核心功能

### 1. 用户认证
- **JWT Token**: OAuth2 Password Bearer 模式
- **密码策略**: 最少8位，需包含大小写字母和数字
- **登录限流**: 5次/分钟 (SlowAPI)
- **Cookie**: 7天有效期的 httpOnly Cookie

### 2. 文件上传
- **支持格式**: 常见音视频格式 (通过 ALLOWED_EXTENSIONS 配置)
- **文件验证**: 扩展名 + 文件签名校验
- **大小限制**: 2GB (MAX_UPLOAD_SIZE)
- **存储**: 按用户 ID 分目录存储

### 3. 文件下载
- **直接下载**: StreamingResponse 流式下载
- **临时链接**: 5分钟有效期的签名下载链接 (HMAC)
- **文件信息**: 通过 ffprobe 获取音视频元数据

### 4. FFmpeg 处理
**支持的参数:**
- 视频编码器: libx264, libx265, libaom-av1, vp9, copy
- 音频编码器: aac, mp3, opus, flac, copy
- 容器格式: mp4, mkv, mov, mp3, flac, wav, aac, ogg
- 裁剪: startTime, endTime
- 分辨率: width x height
- 码率: videoBitrate, audioBitrate
- 预设: superfast/fast/balanced/quality/slow

**硬件加速支持:**
- NVIDIA NVENC (h264_nvenc, hevc_nvenc)
- Intel QSV (h264_qsv, hevc_qsv)
- AMD AMF (h264_amf, hevc_amf)
- Apple VideoToolbox (h264_videotoolbox, hevc_videotoolbox)
- VAAPI (h264_vaapi, hevc_vaapi)

### 5. 任务队列
- **队列机制**: Python asyncio.Queue
- **后台 Worker**: 异步任务处理
- **实时进度**: WebSocket 推送
- **任务管理**: 暂停、取消、删除

---

## 启动方式

```bash
# 推荐方式 (项目根目录)
python run.py

# 或直接运行 backend
python runtime/run_backend.py

# 或使用 uv
uv run uvicorn backend.app.main:app --reload
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DATABASE_URL | 数据库连接 | sqlite:///./ffmpeg_ui.db |
| SECRET_KEY | JWT 密钥 | (必需) |
| CORS_ORIGINS | CORS 允许的域名 | http://localhost:5173 |
| UPLOAD_DIRECTORY | 上传目录 | ./uploads |

---

## 技术栈

- **框架**: FastAPI
- **数据库**: SQLAlchemy + SQLite
- **数据验证**: Pydantic
- **认证**: python-jose (JWT), passlib (bcrypt)
- **限流**: SlowAPI
- **ASGI**: Uvicorn
