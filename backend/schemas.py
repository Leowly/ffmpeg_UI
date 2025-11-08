# backend/schemas.py - Pydantic models for data validation
from typing import Optional, List, TypeVar, Generic, Any
from pydantic import BaseModel, Field

# 创建一个泛型类型变量
T = TypeVar('T')

# --- 新增：标准API响应模型 ---
class APIResponse(BaseModel, Generic[T]):
    """标准化的API响应模型"""
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None

# --- 新增：FFProbe 解析后的响应模型 ---
class FileStreamInfo(BaseModel):
    # 通用字段
    codec_type: str
    codec_name: str
    codec_long_name: str
    bit_rate: Optional[str] = None
    
    # 视频专用字段
    width: Optional[int] = None
    height: Optional[int] = None
    r_frame_rate: Optional[str] = None
    
    # 音频专用字段
    sample_rate: Optional[str] = None
    channels: Optional[int] = None
    channel_layout: Optional[str] = None

    class Config:
        from_attributes = True

class FileFormatInfo(BaseModel):
    format_name: str
    format_long_name: str
    duration: str
    size: str
    bit_rate: str

    class Config:
        from_attributes = True

class FileInfoResponse(BaseModel):
    streams: List[FileStreamInfo]
    format: FileFormatInfo

    class Config:
        extra = 'ignore' # Pydantic v2 asekera, yoksayar bilinmeyen alanları

# --- File Schemas ---

class FileBase(BaseModel):
    filename: str
    filepath: str
    status: str = "uploaded"

class FileCreate(FileBase):
    pass

class File(FileBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True

# --- Frontend Specific File Response Schema ---
class FileResponseInner(BaseModel):
    file_id: str
    original_name: str
    temp_path: str

class FileResponseForFrontend(BaseModel):
    uid: str
    id: str
    name: str
    status: str
    size: int
    response: FileResponseInner

    class Config:
        from_attributes = True

# --- Process Payload Schemas ---
class Resolution(BaseModel):
    width: int
    height: int
    keepAspectRatio: bool

class ProcessPayload(BaseModel):
    files: List[str]
    container: str
    startTime: float
    endTime: float
    totalDuration: float
    videoCodec: str
    audioCodec: str
    videoBitrate: Optional[int] = None
    resolution: Optional[Resolution] = None
    audioBitrate: Optional[int] = None

# --- Task Schemas ---
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
    progress: int
    result_file_id: int | None = None
    result_file: Optional['File'] = None

    class Config:
        from_attributes = True

# --- User Schemas ---

class UserBase(BaseModel):
    """所有用户共有的基本模型"""
    username: str = Field(..., min_length=1, max_length=50)

class UserCreate(UserBase):
    """创建用户时使用的数据模型，包含密码"""
    password: str = Field(..., min_length=6, max_length=72)

class User(UserBase):
    """从API返回用户信息时使用的数据模型，不包含密码"""
    id: int
    files: List[File] = []
    tasks: List[Task] = []

    class Config:
        from_attributes = True

# --- Token Schemas ---

class Token(BaseModel):
    """令牌响应模型"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """令牌数据模型，代表JWT的载荷"""
    username: Optional[str] = None