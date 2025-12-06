import os
import sys

# =========================================================================
# 【修复】预设环境变量uv run --project backend python -m pytest backend/tests/test_ffmpeg_command.py
# 必须在导入 backend.routers.files 之前执行，否则 security.py 会报错
# =========================================================================
os.environ["SECRET_KEY"] = "test_secret_key_for_unit_testing_only"
os.environ["ENABLE_HARDWARE_ACCELERATION_DETECTION"] = "true"

import pytest
from unittest.mock import patch
from backend.routers.files import construct_ffmpeg_command # pyright: ignore[reportMissingImports]
from backend import schemas # pyright: ignore[reportMissingImports]

# --- 辅助函数：快速创建测试用的 Payload ---
def create_payload(
    files=["1"],
    container="mp4",
    videoCodec="libx264",
    audioCodec="aac",
    useHardwareAcceleration=False,
    preset="balanced",
    resolution=None
):
    return schemas.ProcessPayload(
        files=files,
        container=container,
        startTime=0,
        endTime=100,
        totalDuration=100,
        videoCodec=videoCodec,
        audioCodec=audioCodec,
        useHardwareAcceleration=useHardwareAcceleration,
        preset=preset,
        resolution=resolution
    )

# --- 测试用例 ---

def test_cpu_basic_encoding():
    """测试 1: 基础 CPU 编码，不应包含任何硬件加速参数"""
    payload = create_payload(useHardwareAcceleration=False, videoCodec="libx264", preset="balanced")
    
    # Mock 掉检测函数
    with patch('backend.routers.files.detect_video_codec', return_value="h264"):
        cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
    
    cmd_str = " ".join(cmd)
    
    # 验证
    assert "-hwaccel" not in cmd_str
    assert "-c:v libx264" in cmd_str
    assert "-preset medium" in cmd_str  # balanced 对应 CPU 的 medium
    assert "-c:a aac" in cmd_str

@patch('backend.routers.files.detect_hardware_encoder')
@patch('backend.routers.files.detect_video_codec')
def test_nvidia_standard_encoding(mock_video_codec, mock_hw_encoder):
    """测试 2: NVIDIA 标准 H264 输入 -> H264 输出 (应开启零拷贝)"""
    mock_hw_encoder.return_value = "nvidia"
    mock_video_codec.return_value = "h264" 
    
    payload = create_payload(
        useHardwareAcceleration=True, 
        videoCodec="libx264", 
        preset="balanced"
    )
    
    cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
    cmd_str = " ".join(cmd)
    
    # 验证关键点
    assert "-hwaccel cuda" in cmd_str
    assert "-hwaccel_output_format cuda" in cmd_str  # 零拷贝关键参数
    assert "-c:v h264_nvenc" in cmd_str              # 自动映射成功
    assert "-preset p4" in cmd_str                   # balanced 对应 Nvidia 的 p4

@patch('backend.routers.files.detect_hardware_encoder')
@patch('backend.routers.files.detect_video_codec')
def test_nvidia_av1_input_hybrid_mode(mock_video_codec, mock_hw_encoder):
    """测试 3: [关键修复] NVIDIA 遇到 AV1 输入 (应禁用输入硬解，保留输出硬压)"""
    mock_hw_encoder.return_value = "nvidia"
    mock_video_codec.return_value = "av1" # 输入是 AV1
    
    payload = create_payload(
        useHardwareAcceleration=True, 
        videoCodec="libx265", # 输出想要 HEVC
        preset="fast"
    )
    
    cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
    cmd_str = " ".join(cmd)
    
    # 验证关键点
    assert "-hwaccel cuda" not in cmd_str            # 必须禁用输入端硬解！
    assert "-c:v hevc_nvenc" in cmd_str              # 输出端依然要是显卡编码
    assert "-preset p1" in cmd_str                   # fast 对应 Nvidia 的 p1

@patch('backend.routers.files.detect_hardware_encoder')
@patch('backend.routers.files.detect_video_codec')
def test_nvidia_scaling_logic(mock_video_codec, mock_hw_encoder):
    """测试 4: NVIDIA 缩放逻辑 (Zero-Copy时用 GPU 滤镜，AV1 时回退 CPU 滤镜)"""
    mock_hw_encoder.return_value = "nvidia"
    res = schemas.Resolution(width=1280, height=720, keepAspectRatio=True)
    
    # 场景 A: 普通输入 (Zero-Copy 开启) -> 应使用 scale_cuda
    mock_video_codec.return_value = "h264"
    payload_a = create_payload(useHardwareAcceleration=True, resolution=res)
    cmd_a = construct_ffmpeg_command("input.mp4", "output.mp4", payload_a)
    cmd_str_a = " ".join(cmd_a)
    assert "scale_cuda=1280:720" in cmd_str_a
    assert "-s 1280x720" not in cmd_str_a

    # 场景 B: AV1 输入 (Zero-Copy 关闭) -> 应回退到 -s
    mock_video_codec.return_value = "av1"
    payload_b = create_payload(useHardwareAcceleration=True, resolution=res)
    cmd_b = construct_ffmpeg_command("input.mp4", "output.mp4", payload_b)
    cmd_str_b = " ".join(cmd_b)
    assert "scale_cuda" not in cmd_str_b
    assert "-s 1280x720" in cmd_str_b

@patch('backend.routers.files.detect_hardware_encoder')
@patch('backend.routers.files.detect_video_codec')
def test_cpu_fallback_preset_logic(mock_video_codec, mock_hw_encoder):
    """测试 5: 当硬件不支持时回退到 CPU，Preset 不应报错 (不能出现 p1)"""
    # 模拟用户开启了硬件加速，但是 detect_hardware_encoder 返回 None (没显卡)
    mock_hw_encoder.return_value = None 
    mock_video_codec.return_value = "h264"
    
    payload = create_payload(
        useHardwareAcceleration=True, 
        videoCodec="libx264", 
        preset="fast"
    )
    
    cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
    cmd_str = " ".join(cmd)
    
    # 验证
    assert "-hwaccel" not in cmd_str
    assert "-c:v libx264" in cmd_str
    # 关键：Hardware=True + Preset=Fast，但在无显卡时，应使用 superfast (CPU) 而不是 p1 (Nvidia)
    assert "-preset superfast" in cmd_str 
    assert "-preset p1" not in cmd_str

def test_audio_extraction():
    """测试 6: 纯音频提取"""
    payload = create_payload(container="mp3", audioCodec="libmp3lame")
    
    with patch('backend.routers.files.detect_video_codec', return_value="h264"):
        cmd = construct_ffmpeg_command("input.mp4", "output.mp3", payload)
    
    cmd_str = " ".join(cmd)
    
    assert "-vn" in cmd_str            # 禁用视频流
    assert "-c:a libmp3lame" in cmd_str
    assert "-c:v" not in cmd_str       # 不应包含视频编码器参数

@patch('backend.routers.files.detect_hardware_encoder')
@patch('backend.routers.files.detect_video_codec')
def test_intel_qsv_encoding(mock_video_codec, mock_hw_encoder):
    """测试 7: Intel QSV 编码"""
    mock_hw_encoder.return_value = "intel"
    mock_video_codec.return_value = "h264"
    
    payload = create_payload(
        useHardwareAcceleration=True, 
        videoCodec="libx264", 
        preset="balanced"
    )
    
    cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
    cmd_str = " ".join(cmd)
    
    assert "-hwaccel qsv" in cmd_str
    assert "-hwaccel_output_format qsv" in cmd_str
    assert "-c:v h264_qsv" in cmd_str
    assert "-preset medium" in cmd_str