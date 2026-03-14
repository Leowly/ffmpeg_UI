# backend/app/core/deps.py

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .. import models as models_module
from .. import crud as crud_module
from . import security
from .database import SessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_token_from_query_or_header(request: Request) -> str:
    token = request.query_params.get("token")
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    return ""


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(get_token_from_query_or_header),
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
