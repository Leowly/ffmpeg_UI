# main.py - FastAPI app entry point
import os
import sys
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from slowapi.errors import RateLimitExceeded

from .database import engine
from . import models
from .routers import users, files, tasks
from .processing import manager
from .config import UPLOAD_DIRECTORY
from .limiter import limiter, _rate_limit_exceeded_handler

# 在应用启动初期加载环境变量
load_dotenv()

# --- App Initialization ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

# 附加 limiter 状态并添加异常处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Global Configurations ---
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# --- CORS Middleware ---
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
app.include_router(users.router)
app.include_router(files.router)
app.include_router(tasks.router)

# --- WebSocket Endpoint ---
@app.websocket("/ws/progress/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: int):
    await manager.connect(websocket, task_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(task_id)

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the FFmpeg UI Backend"}