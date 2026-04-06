# backend/app/schemas/system.py - System schemas
from typing import Optional, TypeVar, Generic
from pydantic import BaseModel

# 创建一个泛型类型变量
T = TypeVar("T")


# --- 标准API响应模型 ---
class APIResponse(BaseModel, Generic[T]):
    """标准化的API响应模型"""

    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


# --- FFProbe 解析后的响应模型 ---
class FileStreamInfo(BaseModel):
    codec_type: str
    codec_name: Optional[str] = None
    codec_long_name: Optional[str] = None
    bit_rate: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    r_frame_rate: Optional[str] = None
    sample_rate: Optional[str] = None
    channels: Optional[int] = None
    channel_layout: Optional[str] = None

    class Config:
        from_attributes = True


class FileFormatInfo(BaseModel):
    format_name: Optional[str] = None
    format_long_name: Optional[str] = None
    duration: str
    size: str
    bit_rate: str

    class Config:
        from_attributes = True


class FileInfoResponse(BaseModel):
    streams: list[FileStreamInfo]
    format: FileFormatInfo

    class Config:
        extra = "ignore"


class Resolution(BaseModel):
    width: int
    height: int
    keepAspectRatio: bool


class SystemCapabilities(BaseModel):
    has_hardware_acceleration: bool
    hardware_type: Optional[str] = None


class ProcessPayload(BaseModel):
    files: list[str]
    container: str
    startTime: float
    endTime: float
    totalDuration: float
    videoCodec: str
    audioCodec: str
    videoBitrate: Optional[int] = None
    resolution: Optional[Resolution] = None
    audioBitrate: Optional[int] = None

    useHardwareAcceleration: bool = False

    preset: str = "balanced"
