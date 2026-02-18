# backend/app/main.py

import os
import asyncio
import logging
import threading
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from . import models, crud
from .core import config
from .core.database import engine, SessionLocal
from .core.config import UPLOAD_DIRECTORY
from .core.limiter import limiter
from .api import users, files, tasks
from .services.processing import manager, worker
from .services.hw_accel import detect_hardware_encoder

# 只在非测试模式下创建表
if os.environ.get("PYTEST_RUNNING") != "1":
    models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

app.state.limiter = limiter

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

cors_origins_str = os.getenv("CORS_ORIGINS", "")
origins = [origin.strip() for origin in cors_origins_str.split(",") if origin]
if not origins:
    origins = ["http://localhost", "http://localhost:5173"]

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


@app.on_event("startup")
async def startup_event():
    def warmup_hw_detection():
        hw_type = detect_hardware_encoder()
        if hw_type:
            print(f">>> Hardware acceleration detected: {hw_type.upper()}")
        else:
            print(">>> No hardware acceleration detected, using CPU encoding.")

    threading.Thread(target=warmup_hw_detection, daemon=True).start()

    # Clean up stale tasks that were left in processing/pending state due to server restart
    db = SessionLocal()
    try:
        # 查找所有正在进行但因重启而中断的任务
        stale_tasks = (
            db.query(models.ProcessingTask)
            .filter(models.ProcessingTask.status.in_(["processing", "pending"]))
            .all()
        )

        for task in stale_tasks:
            print(f"Marking stale task {task.id} as failed due to server restart.")
            task.status = "failed"
            task.details = "Server restarted while task was pending/processing."
        db.commit()
    except Exception as e:
        print(f"Error cleaning up stale tasks: {e}")
    finally:
        db.close()

    asyncio.create_task(worker())
    print(">>> Background worker started.")


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
