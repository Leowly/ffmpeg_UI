# backend/config.py
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# 加载环境变量
load_dotenv(dotenv_path=ENV_PATH)

# 读取环境变量，默认为 True
ENABLE_HW_ACCEL_DETECTION = (
    os.environ.get("ENABLE_HARDWARE_ACCELERATION_DETECTION", "true").lower() == "true"
)

# 是否启用热重载 (默认 False)
RELOAD = os.environ.get("RELOAD", "false").lower() == "true"

UPLOAD_DIRECTORY = BASE_DIR.parent / "data" / "workspaces"


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
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$", s)
    if not match:
        logger.warning(
            "Invalid MAX_UPLOAD_SIZE format '%s', defaulting to 2GB.", size_str
        )
        return 2 * 1024 * 1024 * 1024

    number = float(match.group(1))
    unit = match.group(2)

    if "G" in unit:
        return int(number * 1024 * 1024 * 1024)
    elif "M" in unit:
        return int(number * 1024 * 1024)
    elif "K" in unit:
        return int(number * 1024)
    else:
        return int(number)


# 获取配置的最大上传限制
MAX_UPLOAD_SIZE = parse_size_to_bytes(os.environ.get("MAX_UPLOAD_SIZE"))

# --- 新增：FFmpeg 支持的常见文件扩展名 ---
# 这是一个非常全面的列表，涵盖了视频、音频和部分图像序列格式
ALLOWED_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",
    ".avi",
    ".wmv",
    ".mpg",
    ".mpeg",
    ".m2ts",
    ".mts",
    ".ts",
    ".vob",
    ".3gp",
    ".3g2",
    ".ogv",
    ".rm",
    ".rmvb",
    ".asf",
    ".divx",
    ".f4v",
    ".h264",
    ".hevc",
    ".mp3",
    ".aac",
    ".flac",
    ".wav",
    ".wave",
    ".ogg",
    ".m4a",
    ".wma",
    ".opus",
    ".alac",
    ".aiff",
    ".ape",
    ".ac3",
    ".dts",
    ".pcm",
    ".amr",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".tiff",
    ".webp",
}

FILE_SIGNATURES = {
    b"ftyp": {"mp4", "m4v", "mov"},
    b"\x1a\x45\xdf\xa3": {"mkv", "webm"},
    b"\xff\xd8\xff": {"jpg", "jpeg"},
    b"\x89PNG\r\n\x1a\n": {"png"},
    b"RIFF": {"avi", "webm", "mkv", "wave", "wav"},
    b"OggS": {"ogg", "ogv", "opus"},
    b"ID3": {"mp3"},
    b"\xff\xfb": {"mp3"},
    b"\xff\xf3": {"mp3"},
    b"\xff\xf5": {"mp3"},
    b"fLaC": {"flac"},
    b"MThd": {"mid", "midi"},
    b"\x30\x26\xb2\x75": {"wmv", "asf"},
}


@lru_cache(maxsize=128)
def reconstruct_file_path(stored_path: str, user_id: int) -> str | None:
    # 处理 Windows 反斜杠
    normalized_path = stored_path.replace("\\", "/")

    # 尝试直接使用存储的路径
    if os.path.exists(normalized_path):
        return normalized_path

    # 尝试相对于项目根目录
    candidate = BASE_DIR.parent / normalized_path
    if candidate.exists():
        return str(candidate)

    # 尝试在用户目录下查找
    filename = os.path.basename(normalized_path)
    user_candidate = UPLOAD_DIRECTORY / str(user_id) / filename
    if user_candidate.exists():
        return str(user_candidate)

    return None


def invalidate_file_path_cache():
    """Invalidate the reconstruct_file_path cache"""
    reconstruct_file_path.cache_clear()
