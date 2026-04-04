# backend/app/core/deps.py


from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import models as models_module
from app import crud as crud_module
from app.core import security
from app.core.database import SessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_token_from_header_or_cookie(request: Request) -> str:
    """
    获取访问令牌（拒绝 URL Query 传参以防日志泄露）
    优先从 Authorization Header 获取，其次从 HttpOnly Cookie 获取
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return ""


def get_current_user(
    db: Session = Depends(get_db),
    # 【修改点】：对应修改依赖注入的函数名
    token: str = Depends(get_token_from_header_or_cookie),
) -> models_module.User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = security.verify_token(token, credentials_exception)
    username: str | None = token_data.get("sub")
    if username is None:
        raise credentials_exception
    user = crud_module.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user
