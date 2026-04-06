# backend/app/schemas/__init__.py
import sys
from types import SimpleNamespace
from app.schemas.user import UserBase, UserCreate, User, Token, TokenData
from app.schemas.file import (
    FileBase,
    FileCreate,
    File,
    FileResponseInner,
    FileResponseForFrontend,
)
from app.schemas.task import TaskBase, TaskCreate, Task
from app.schemas.system import (
    APIResponse,
    FileStreamInfo,
    FileFormatInfo,
    FileInfoResponse,
    Resolution,
    SystemCapabilities,
    ProcessPayload,
)

schemas = SimpleNamespace(
    APIResponse=APIResponse,
    FileStreamInfo=FileStreamInfo,
    FileFormatInfo=FileFormatInfo,
    FileInfoResponse=FileInfoResponse,
    FileBase=FileBase,
    FileCreate=FileCreate,
    File=File,
    FileResponseInner=FileResponseInner,
    FileResponseForFrontend=FileResponseForFrontend,
    Resolution=Resolution,
    SystemCapabilities=SystemCapabilities,
    ProcessPayload=ProcessPayload,
    TaskBase=TaskBase,
    TaskCreate=TaskCreate,
    Task=Task,
    UserBase=UserBase,
    UserCreate=UserCreate,
    User=User,
    Token=Token,
    TokenData=TokenData,
)

__all__ = [
    "APIResponse",
    "FileStreamInfo",
    "FileFormatInfo",
    "FileInfoResponse",
    "FileBase",
    "FileCreate",
    "File",
    "FileResponseInner",
    "FileResponseForFrontend",
    "Resolution",
    "SystemCapabilities",
    "ProcessPayload",
    "TaskBase",
    "TaskCreate",
    "Task",
    "UserBase",
    "UserCreate",
    "User",
    "Token",
    "TokenData",
    "schemas",
]
