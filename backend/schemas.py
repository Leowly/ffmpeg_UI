# schemas.py - Pydantic models for data validation
from typing import Optional
from pydantic import BaseModel, Field

# --- User Schemas ---

class UserBase(BaseModel):
    """所有用户共有的基本模型"""
    username: str = Field(..., min_length=3, max_length=50)

class UserCreate(UserBase):
    """创建用户时使用的数据模型，包含密码"""
    password: str = Field(..., min_length=8, max_length=72)

class User(UserBase):
    """从API返回用户信息时使用的数据模型，不包含密码"""
    id: int

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