# schemas.py - Pydantic models for data validation
from typing import Optional, List
from pydantic import BaseModel, Field

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
    files: List[File] = [] # Add files to User schema

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