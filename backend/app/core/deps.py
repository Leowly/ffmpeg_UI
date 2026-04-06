# backend/app/core/deps.py


from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.models.models import User
from app.crud.crud_user import get_user_by_username
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
) -> User:
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
    user = get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user


async def get_valid_file_for_user(
    file_id: int,
    user_id: int,
    db: Session,
) -> tuple:
    """校验文件归属并解析物理路径，返回 (db_file, resolved_path)。"""
    from app.crud.crud_file import get_file_by_id
    from app.core.config import reconstruct_file_path
    from app.core.exceptions import ResourceNotFoundError

    db_file = get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != user_id:
        raise ResourceNotFoundError(detail="File not found or access denied")

    resolved_path = await reconstruct_file_path_async(str(db_file.filepath), user_id)
    if not resolved_path:
        raise ResourceNotFoundError(detail="Physical file missing on server")

    return db_file, resolved_path


async def reconstruct_file_path_async(stored_path: str, user_id: int) -> str | None:
    """异步包装 reconstruct_file_path，避免阻塞事件循环。"""
    import asyncio
    from app.core.config import reconstruct_file_path

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, reconstruct_file_path, stored_path, user_id)
