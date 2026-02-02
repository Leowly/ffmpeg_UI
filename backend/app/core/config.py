# backend/config.py
import os
import re
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# 加载环境变量
load_dotenv(dotenv_path=ENV_PATH)

# 读取环境变量，默认为 True
ENABLE_HW_ACCEL_DETECTION = os.environ.get("ENABLE_HARDWARE_ACCELERATION_DETECTION", "true").lower() == "true"

UPLOAD_DIRECTORY = "./backend/workspaces"

# --- 新增：文件大小解析逻辑 ---
def parse_size_to_bytes(size_str: str | int | None) -> int:
    """
    解析文件大小配置，支持数字(bytes)或带单位的字符串(GB, MB, KB)。
    默认为 2GB (2 * 1024 * 1024 * 1024)。
    """
    if size_str is None:
        return 2 * 1024 * 1024 * 1024  # 默认 2GB
    
    # 如果已经是数字（int），直接返回
    if isinstance(size_str, int):
        return size_str

    s = str(size_str).strip().upper()
    if s.isdigit():
        return int(s)

    # 正则匹配 数字 + 单位
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', s)
    if not match:
        print(f"Warning: Invalid MAX_UPLOAD_SIZE format '{size_str}', defaulting to 2GB.")
        return 2 * 1024 * 1024 * 1024

    number = float(match.group(1))
    unit = match.group(2)

    if 'G' in unit:
        return int(number * 1024 * 1024 * 1024)
    elif 'M' in unit:
        return int(number * 1024 * 1024)
    elif 'K' in unit:
        return int(number * 1024)
    else:
        return int(number)

# 获取配置的最大上传限制
MAX_UPLOAD_SIZE = parse_size_to_bytes(os.environ.get("MAX_UPLOAD_SIZE"))

# --- 新增：FFmpeg 支持的常见文件扩展名 ---
# 这是一个非常全面的列表，涵盖了视频、音频和部分图像序列格式
ALLOWED_EXTENSIONS = {
    # Video Formats
    '.mp4', '.m4v', '.mov', '.mkv', '.webm', '.flv', '.avi', '.wmv', 
    '.mpg', '.mpeg', '.m2ts', '.mts', '.ts', '.vob', '.3gp', '.3g2',
    '.ogv', '.rm', '.rmvb', '.asf', '.divx', '.f4v', '.h264', '.hevc',
    # Audio Formats
    '.mp3', '.aac', '.flac', '.wav', '.ogg', '.m4a', '.wma', '.opus',
    '.alac', '.aiff', '.ape', '.ac3', '.dts', '.pcm', '.amr',
    # Image/Sequence Formats (FFmpeg can process these)
    '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'
}

@lru_cache(maxsize=128)
def reconstruct_file_path(stored_path: str, user_id: int) -> str | None:
    # 确保上传目录存在
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

    if os.path.exists(stored_path):
        return stored_path

    expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(user_id))
    unique_filename = os.path.basename(stored_path)
    reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)

    if os.path.exists(reconstructed_file_path):
        return reconstructed_file_path

    return None


def invalidate_file_path_cache():
    """Invalidate the reconstruct_file_path cache"""
    reconstruct_file_path.cache_clear()