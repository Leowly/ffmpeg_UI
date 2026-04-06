# backend/app/schemas/task.py - Task schemas
from typing import Optional
from pydantic import BaseModel

from app.schemas.file import File


class TaskBase(BaseModel):
    ffmpeg_command: str
    source_filename: str | None = None


class TaskCreate(TaskBase):
    pass


class Task(TaskBase):
    id: int
    output_path: str | None
    status: str
    details: str | None
    owner_id: int
    result_file_id: int | None = None
    result_file: Optional[File] = None

    class Config:
        from_attributes = True
