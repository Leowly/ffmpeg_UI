# 下载模块

import asyncio
import json
import os
from typing import List, Tuple

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..crud import crud
from ..models import models
from ..schemas import schemas
from ..core.deps import get_current_user, get_db
from ..core.config import reconstruct_file_path

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
            clean_data = schemas.FileInfoResponse.model_validate(raw_data)
            return clean_data
        except (json.JSONDecodeError, Exception):
            raise HTTPException(
                status_code=500, detail="Could not parse ffprobe output"
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
