# backend/app/main.py

import os
import sys
import asyncio
import logging
import threading
from pathlib import Path
from contextlib import asynccontextmanager

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / ".env"
from dotenv import load_dotenv

load_dotenv(env_path)

# 配置日志 - 与 uvicorn/FastAPI 格式保持一致
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)
logger = logging.getLogger(__name__)

# Windows 事件循环策略配置（必须在导入 uvicorn/FastAPI 之前）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app import models
from app.core.database import engine, SessionLocal
from app.core.config import UPLOAD_DIRECTORY, BASE_DIR
from app.core.limiter import limiter
from app.api import users, files, tasks
from app.services import manager, worker
from app.services.hw_accel import detect_hardware_encoder

# 只在非测试模式下创建表
if os.environ.get("PYTEST_RUNNING") != "1":
    models.Base.metadata.create_all(bind=engine)

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

cors_origins_str = os.getenv("CORS_ORIGINS", "")
origins = [origin.strip() for origin in cors_origins_str.split(",") if origin]
if not origins:
    origins = ["http://localhost", "http://localhost:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    def warmup_hw_detection():
        hw_type = detect_hardware_encoder()
        if hw_type:
            logger.info("Hardware acceleration detected: %s", hw_type.upper())
        else:
            logger.info("No hardware acceleration detected, using CPU encoding.")

    threading.Thread(target=warmup_hw_detection, daemon=True).start()

    # Clean up stale tasks that were left in processing/pending state due to server restart
    db = SessionLocal()
    try:
        stale_tasks = (
            db.query(models.ProcessingTask)
            .filter(models.ProcessingTask.status.in_(["processing", "pending"]))
            .all()
        )

        for task in stale_tasks:
            logger.warning(
                "Marking stale task %s as failed due to server restart.", task.id
            )
            task.status = "failed"
            task.details = "Server restarted while task was pending/processing."
        db.commit()
    except Exception as e:
        logger.error("Error cleaning up stale tasks: %s", e)
    finally:
        db.close()

    max_concurrent_workers = int(os.getenv("MAX_CONCURRENT_WORKERS", "1"))
    for i in range(max_concurrent_workers):
        asyncio.create_task(worker(worker_id=i + 1))
    logger.info("%s background worker(s) started.", max_concurrent_workers)

    yield


app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


app.include_router(users.router)  # 用户路由通常在根路径，如 /token, /users/
app.include_router(files.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")


@app.websocket("/ws/progress/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: int):
    await manager.connect(websocket, task_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(task_id)


FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@app.get("/{full_path:path}", tags=["SPA"])
async def serve_spa(full_path: str):
    requested_file = FRONTEND_DIST / full_path
    if requested_file.is_file():
        return FileResponse(requested_file)

    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return {"error": "Frontend not built"}


def start(host: str = "127.0.0.1", port: int = 8000, reload: bool | None = None):
    import uvicorn
    from app.core.config import RELOAD as config_reload

    use_reload = reload if reload is not None else config_reload

    reload_excludes = None
    if use_reload:
        data_dir = str(BASE_DIR / "data")
        reload_excludes = [data_dir]

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=use_reload,
        reload_excludes=reload_excludes,
    )


if __name__ == "__main__":
    start()
