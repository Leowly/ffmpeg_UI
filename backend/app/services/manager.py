# backend/app/services/manager.py

from typing import Dict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, task_id: int):
        await websocket.accept()
        self.active_connections[task_id] = websocket

    def disconnect(self, task_id: int):
        if task_id in self.active_connections:
            del self.active_connections[task_id]

    async def send_progress(
        self, task_id: int, progress: int, status: str | None = None
    ):
        if task_id in self.active_connections:
            message = {"progress": progress}
            if status:
                message["status"] = status
            await self.active_connections[task_id].send_json(message)


manager = ConnectionManager()
