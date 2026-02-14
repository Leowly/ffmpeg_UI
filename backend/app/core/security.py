# security.py - Password hashing and user authentication
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

# 1. 创建一个 CryptContext 实例，并指定 bcrypt 为默认算法
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# 2. 从环境变量中读取JWT配置，不提供默认值以确保生产环境安全
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 90))

# 3. 检查必需的环境变量，如果缺失则阻止启动
if not SECRET_KEY:
    raise ValueError(
        "\n\n"
        "===============================================\n"
        "❌ CRITICAL SECURITY ERROR: SECRET_KEY is not set!\n"
        "===============================================\n"
        "Please set the SECRET_KEY in your .env file.\n"
        "This is required for secure authentication.\n"
        "\n"
        "To fix this:\n"
        "1. Open your .env file in the project root\n"
        "2. Add: SECRET_KEY=your-super-secret-key-here\n"
        "   (Use a strong random key, at least 32 characters)\n"
        "3. Restart the application\n"
        "\n"
        "Example (use a unique key in production!):\n"
        "SECRET_KEY=3x4mpl3v3rys3cur3k3yf0rpr0d3nv1r0nm3nt\n"
        "===============================================\n"
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希后的密码匹配"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """将明文密码哈希处理"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, credentials_exception) -> dict:
    """验证JWT令牌并返回载荷"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise credentials_exception
