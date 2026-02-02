# 上传模块

import asyncio
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Request, status
from sqlalchemy.orm import Session

from ..crud import crud
from ..models import models
from ..schemas import schemas
from ..core.deps import get_current_user, get_db
from ..core.config import (
    UPLOAD_DIRECTORY,
    MAX_UPLOAD_SIZE,
    ALLOWED_EXTENSIONS,
)

router = APIRouter(
    tags=["Files"],
)


@router.post("/upload", response_model=schemas.FileResponseForFrontend)
async def upload_file(
    request: Request,
    file: UploadFile,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # --- [第一道防线] 检查 Content-Length ---
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件过大。限制为 {MAX_UPLOAD_SIZE / (1024 * 1024):.2f} MB",
                )
        except ValueError:
            pass

    # --- [第二道防线] 检查文件扩展名 ---
    filename = file.filename or ""
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}。仅支持常见的音视频文件。",
        )

    try:
        file_extension = ext
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        user_upload_directory = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        os.makedirs(user_upload_directory, exist_ok=True)
        file_location = os.path.normpath(
            os.path.join(user_upload_directory, unique_filename)
        )

        current_size = 0
        async with aiofiles.open(file_location, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunk
                if not chunk:
                    break

                current_size += len(chunk)
                if current_size > MAX_UPLOAD_SIZE:
                    await out_f.close()
                    if os.path.exists(file_location):
                        os.remove(file_location)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件实际大小超过限制 ({MAX_UPLOAD_SIZE / (1024 * 1024):.2f} MB)",
                    )

                await out_f.write(chunk)

        loop = asyncio.get_running_loop()
        file_size = await loop.run_in_executor(None, os.path.getsize, file_location)

        try:

            def db_create():
                return crud.create_user_file(
                    db=db,
                    file=schemas.FileCreate(
                        filename=filename,
                        filepath=file_location,
                        status="uploaded",
                    ),
                    user_id=current_user.id,
                )

            db_file = await loop.run_in_executor(None, db_create)
        except Exception as e:
            if os.path.exists(file_location):
                os.remove(file_location)
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        return schemas.FileResponseForFrontend(
            uid=str(db_file.id),
            id=str(db_file.id),
            name=db_file.filename,
            status="done",
            size=file_size,
            response=schemas.FileResponseInner(
                file_id=str(db_file.id),
                original_name=db_file.filename,
                temp_path=db_file.filepath,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        if "file_location" in locals() and os.path.exists(file_location):
            try:
                os.remove(file_location)
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=f"Could not upload file: {str(e)}")
