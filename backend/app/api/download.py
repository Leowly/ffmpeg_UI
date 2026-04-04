# 下载模块

import asyncio
import json
import os
from typing import List, Tuple

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.crud import crud
from app.models import models
from app.schemas import schemas
from app.core.deps import get_current_user, get_db
from app.core.config import reconstruct_file_path
from app.core.security import create_download_token, verify_download_token
from app.core.database import SessionLocal

router = APIRouter(
    tags=["Files"],
)


def run_ffprobe_sync(path: str) -> Tuple[int, str, str]:
    """同步运行 ffprobe 获取文件信息"""
    import subprocess

    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            creationflags=0,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        raise


@router.get("/file-info", response_model=schemas.FileInfoResponse)
async def get_file_info(
    filename: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        file_id = int(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = db_file.filepath
    resolved = await asyncio.get_running_loop().run_in_executor(
        None, reconstruct_file_path, file_path, current_user.id
    )
    if not resolved:
        raise HTTPException(status_code=404, detail="File not found on server")
    file_path = resolved

    try:
        loop = asyncio.get_running_loop()
        returncode, stdout, stderr = await loop.run_in_executor(
            None, run_ffprobe_sync, file_path
        )

        if returncode != 0:
            raise HTTPException(status_code=500, detail=f"ffprobe error: {stderr}")

        try:
            raw_data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500, detail=f"ffprobe returned invalid JSON: {str(e)}"
            )

        try:
            clean_data = schemas.FileInfoResponse.model_validate(raw_data)
            return clean_data
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"ffprobe output validation failed: {str(e)}")
            logger.debug(f"Raw ffprobe output: {stdout[:500]}")
            raise HTTPException(
                status_code=500,
                detail=f"ffprobe output doesn't match expected schema: {str(e)}",
            )

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffprobe command not found.")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@router.get("/files", response_model=List[schemas.FileResponseForFrontend])
async def read_user_files(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    db_files = crud.get_user_files(db, user_id=current_user.id)
    response_files = []
    loop = asyncio.get_running_loop()

    for db_file in db_files:
        current_file_path = db_file.filepath
        resolved_file_path = None

        exists = await loop.run_in_executor(None, os.path.exists, current_file_path)
        if exists:
            resolved_file_path = current_file_path
        else:
            resolved_candidate = await loop.run_in_executor(
                None, reconstruct_file_path, current_file_path, current_user.id
            )
            if resolved_candidate:
                resolved_file_path = resolved_candidate

        if resolved_file_path:
            file_size = await loop.run_in_executor(
                None, os.path.getsize, resolved_file_path
            )
            response_files.append(
                schemas.FileResponseForFrontend(
                    uid=str(db_file.id),
                    id=str(db_file.id),
                    name=db_file.filename,
                    status=db_file.status,
                    size=file_size,
                    response=schemas.FileResponseInner(
                        file_id=str(db_file.id),
                        original_name=db_file.filename,
                        temp_path=resolved_file_path,
                    ),
                )
            )

    return response_files


@router.get("/download-file/{file_id}")
async def download_file(
    file_id: str,
    token: str | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        file_id_int = int(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    db_file = crud.get_file_by_id(db, file_id=file_id_int)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = db_file.filepath
    loop = asyncio.get_running_loop()
    resolved = await loop.run_in_executor(
        None, reconstruct_file_path, file_path, current_user.id
    )
    if resolved:
        file_path = resolved
    else:
        raise HTTPException(status_code=404, detail="File not found on server")

    async def file_iterator(path: str, chunk_size: int = 1024 * 1024):
        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    headers = {"Content-Disposition": f'attachment; filename="{db_file.filename}"'}
    return StreamingResponse(
        file_iterator(file_path), media_type="application/octet-stream", headers=headers
    )


@router.get("/download-temp/{file_id}")
async def get_temp_download_link(
    file_id: str,
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    try:
        file_id_int = int(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    db = SessionLocal()
    try:
        db_file = crud.get_file_by_id(db, file_id=file_id_int)
        if not db_file or db_file.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="File not found")
    finally:
        db.close()

    token = create_download_token(file_id_int, int(current_user.id), expires_minutes=5)
    base_url = str(request.base_url).rstrip("/")
    temp_url = f"{base_url}/api/temp-download/{token}"
    return {"temp_url": temp_url}


@router.get("/temp-download/{token}")
async def temp_download(
    token: str,
    db: Session = Depends(get_db),
):
    """临时下载端点（验证签名，无需认证）"""
    payload = verify_download_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired download link")

    file_id = payload.get("file_id")
    user_id = payload.get("user_id")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != user_id:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = db_file.filepath
    loop = asyncio.get_running_loop()
    resolved = await loop.run_in_executor(
        None, reconstruct_file_path, file_path, user_id
    )
    if resolved:
        file_path = resolved
    else:
        raise HTTPException(status_code=404, detail="File not found on server")

    file_size = await loop.run_in_executor(None, os.path.getsize, file_path)

    async def file_iterator(path: str, chunk_size: int = 1024 * 1024):
        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{db_file.filename}"',
        "Content-Length": str(file_size),
    }
    return StreamingResponse(
        file_iterator(file_path), media_type="application/octet-stream", headers=headers
    )
