# backend/limiter.py

from slowapi import Limiter
from slowapi.util import get_remote_address

# 创建一个全局的 limiter 实例
# "5/minute" 表示每分钟最多允许 5 次请求
limiter = Limiter(key_func=get_remote_address, default_limits=["5/minute"])