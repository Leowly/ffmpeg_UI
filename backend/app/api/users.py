# backend/app/api/users.py

from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.crud import crud
from app.models import models
from app.schemas.user import UserCreate, User
from app.schemas.system import APIResponse
from app.schemas.user import Token
from app.core import security
from app.core.deps import get_db, get_current_user
from app.core.limiter import limiter

router = APIRouter()


@router.post("/token", response_model=APIResponse[Token], tags=["Users"])
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    try:
        user = crud.get_user_by_username(db, username=form_data.username)

        hashed_password = (
            user.hashed_password
            if user
            else security.get_password_hash("a_dummy_password_that_will_never_match")
        )
        is_password_correct = security.verify_password(
            form_data.password, cast(str, hashed_password)
        )

        if not user or not is_password_correct:
            error_response = APIResponse(success=False, message="用户名或密码不正确。")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_response.model_dump(),
            )

        access_token = security.create_access_token(data={"sub": user.username})
        token_data = Token(access_token=access_token, token_type="bearer")
        success_response = APIResponse[Token](
            success=True, data=token_data, message="登录成功！"
        )
        response = JSONResponse(
            status_code=status.HTTP_200_OK, content=success_response.model_dump()
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,
        )
        return response

    except SQLAlchemyError:
        error_response = APIResponse(
            success=False, message="数据库连接失败，请稍后再试。"
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response.model_dump(),
        )
    except Exception:
        error_response = APIResponse(success=False, message="服务器发生未知错误。")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
        )


@router.post("/users/", response_model=User, tags=["Users"])
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)


@router.get("/users/me", response_model=User, tags=["Users"])
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/logout", tags=["Users"])
def logout():
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="access_token")
    return response
