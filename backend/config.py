# backend/config.py
import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

# 获取当前文件 (backend/config.py) 的父目录的父目录，即项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# 加载环境变量
load_dotenv(dotenv_path=ENV_PATH)

# 读取环境变量，默认为 True
ENABLE_HW_ACCEL_DETECTION = os.environ.get("ENABLE_HARDWARE_ACCELERATION_DETECTION", "true").lower() == "true"

UPLOAD_DIRECTORY = "./backend/workspaces"

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