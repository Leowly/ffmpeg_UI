# FFmpeg UI 后端测试套件

本目录包含 FFmpeg UI 后端的所有单元测试，按照功能模块组织。

## 测试文件说明

### `test_crud.py`
- 测试 `backend/crud.py` 中的所有 CRUD 操作
- 包括用户、文件和任务的创建、读取、更新和删除操作
- 使用 SQLite 内存数据库进行隔离测试

### `test_processing.py` 
- 测试 `backend/processing.py` 中的处理逻辑
- 包括 FFmpeg 执行、连接管理器和多用户队列功能
- 使用 Mock 对象测试外部依赖

### `test_config.py`
- 测试 `backend/config.py` 中的配置函数
- 包括文件路径重建和缓存功能
- 验证缓存行为和目录创建逻辑

### `test_routes.py`
- 测试各路由模块中的端点函数
- 包括文件上传、下载、处理和任务管理端点
- 使用 FastAPI TestClient 进行端到端测试

### `run_tests.py`
- 一键运行所有测试的脚本
- 提供多种运行模式和覆盖率报告

## 运行测试

### 运行所有测试
```bash
cd tests
python run_tests.py
```

### 运行带覆盖率的测试
```bash
cd tests
python run_tests.py coverage
```

### 列出所有测试
```bash
cd tests
python run_tests.py list
```

### 运行单个测试文件
```bash
cd tests
python -m pytest test_crud.py -v
```

## 测试环境要求

项目使用 uv 包管理器，所有依赖都在主项目的 pyproject.toml 中定义。

安装依赖：
```bash
cd backend
uv sync
```

或者安装开发依赖（包含测试依赖）：
```bash
uv sync --all-extras
```

## 测试覆盖范围

- CRUD 操作的完整测试
- 业务逻辑的边界条件测试
- 错误处理和异常情况测试
- 多用户队列隔离功能测试
- 配置缓存功能测试
- 端到端 API 测试

## 维护指南

当添加新功能时，请确保：
1. 为新功能编写相应的单元测试
2. 测试所有可能的输入和边界条件
3. 测试错误处理和异常情况
4. 运行所有测试确保没有回归问题