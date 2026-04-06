# 上传模块

import asyncio
import uuid
from pathlib import Path
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Request, status
from sqlalchemy.orm import Session

from app.crud import crud
from app.models import models
from app.schemas.file import FileCreate, FileResponseForFrontend, FileResponseInner
from app.core.deps import get_current_user, get_db
from app.core.config import (
    UPLOAD_DIRECTORY,
    MAX_UPLOAD_SIZE,
    ALLOWED_EXTENSIONS,
)
from app.services.file_validator import validate_file_type

router = APIRouter(
    tags=["Files"],
)


@router.post("/upload", response_model=FileResponseForFrontend)
async def upload_file(
    request: Request,
    file: UploadFile,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    filename = file.filename or ""
    _, ext = Path(filename).suffix, Path(filename).suffix
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}。仅支持常见的音视频文件。",
        )

    file_location = None
    try:
        file_extension = ext
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        user_upload_directory = Path(UPLOAD_DIRECTORY) / str(current_user.id)
        user_upload_directory.mkdir(parents=True, exist_ok=True)
        file_location = user_upload_directory / unique_filename

        current_size = 0
        first_chunk = True
        async with aiofiles.open(file_location, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break

                if first_chunk:
                    is_valid, error_msg = await validate_file_type(chunk, ext.lower())
                    if not is_valid:
                        await out_f.close()
                        if file_location.exists():
                            file_location.unlink()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=error_msg,
                        )
                    first_chunk = False

                current_size += len(chunk)
                if current_size > MAX_UPLOAD_SIZE:
                    await out_f.close()
                    if file_location.exists():
                        file_location.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件实际大小超过限制 ({MAX_UPLOAD_SIZE / (1024 * 1024):.2f} MB)",
                    )

                await out_f.write(chunk)

        if current_size == 0:
            if file_location.exists():
                file_location.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件为空或无法读取",
            )

        file_size = file_location.stat().st_size

        try:
            db_file = crud.create_user_file(
                db=db,
                file=FileCreate(
                    filename=filename,
                    filepath=str(file_location),
                    status="uploaded",
                ),
                user_id=int(current_user.id),
            )
        except Exception as e:
            if file_location.exists():
                file_location.unlink()
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        return FileResponseForFrontend(
            uid=str(db_file.id),
            id=str(db_file.id),
            name=str(db_file.filename),
            status="done",
            size=file_size,
            response=FileResponseInner(
                file_id=str(db_file.id),
                original_name=str(db_file.filename),
                temp_path=str(db_file.filepath),
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        if file_location and file_location.exists():
            try:
                file_location.unlink()
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=f"Could not upload file: {str(e)}")
