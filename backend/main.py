# main.py - FastAPI app entry point
import os
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from . import config 
from .database import engine, SessionLocal
from . import models, crud
from .routers import users, files, tasks
from .processing import manager, worker
from .config import UPLOAD_DIRECTORY
from .limiter import limiter

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

app.state.limiter = limiter

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

cors_origins_str = os.getenv("CORS_ORIGINS", "")
origins = [origin.strip() for origin in cors_origins_str.split(',') if origin]
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

# --- Include Routers ---
# 核心修复：在这里添加 prefix="/api"
app.include_router(users.router) # 用户路由通常在根路径，如 /token, /users/
app.include_router(files.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Clean up stale tasks that were left in processing/pending state due to server restart
    db = SessionLocal()
    try:
        # 查找所有正在进行但因重启而中断的任务
        stale_tasks = db.query(models.ProcessingTask).filter(
            models.ProcessingTask.status.in_(['processing', 'pending'])
        ).all()

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

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the FFmpeg UI Backend"}