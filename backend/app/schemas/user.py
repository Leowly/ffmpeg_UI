# backend/app/schemas/user.py - User schemas
from typing import List, Optional
from pydantic import BaseModel, Field, validator
import re


class UserBase(BaseModel):
    """所有用户共有的基本模型"""

    username: str = Field(..., min_length=1, max_length=50)


class UserCreate(UserBase):
    """创建用户时使用的数据模型，包含密码"""

    # 移除复杂的 pattern
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="密码必须至少8位，且包含大小写字母和数字",
    )

    # 添加独立的 validator 函数
    @validator("password")
    def password_complexity(cls, v):
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        return v


class User(UserBase):
    """从API返回用户信息时使用的数据模型，不包含密码"""

    id: int
    files: List["File"] = []  # type: ignore[assignment]
    tasks: List["Task"] = []  # type: ignore[assignment]

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


# Import forward references
from app.schemas.file import File  # noqa: E402
from app.schemas.task import Task  # noqa: E402

User.model_rebuild()
