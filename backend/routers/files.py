# backend/routers/files.py

import asyncio
import json
import os
import subprocess
import uuid
from typing import List, Tuple
import shlex

import aiofiles
from fastapi import (APIRouter, Depends, HTTPException,UploadFile,)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..dependencies import get_current_user, get_db
from ..processing import manager, user_task_queues
from ..config import UPLOAD_DIRECTORY, reconstruct_file_path

router = APIRouter(
    tags=["Files"],
)

def detect_video_codec(input_path: str) -> str:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=nw=1:nk=1",
            input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return ""

@router.get("/file-info", response_model=schemas.FileInfoResponse)
async def get_file_info(
    filename: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
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

    def run_ffprobe_sync(path: str) -> Tuple[int, str, str]:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path,
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, errors='ignore',
                check=False, creationflags=0,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            raise

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
            raise HTTPException(status_code=500, detail="Could not parse ffprobe output")

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffprobe command not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@router.get("/files", response_model=List[schemas.FileResponseForFrontend])
async def read_user_files(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
            resolved_candidate = await loop.run_in_executor(None, reconstruct_file_path, current_file_path, current_user.id)
            if resolved_candidate:
                resolved_file_path = resolved_candidate

        if resolved_file_path:
            file_size = await loop.run_in_executor(None, os.path.getsize, resolved_file_path)
            response_files.append(schemas.FileResponseForFrontend(
                uid=str(db_file.id),
                id=str(db_file.id),
                name=db_file.filename,
                status=db_file.status,
                size=file_size,
                response=schemas.FileResponseInner(
                    file_id=str(db_file.id),
                    original_name=db_file.filename,
                    temp_path=resolved_file_path
                )
            ))

    return response_files

@router.get("/download-file/{file_id}")
async def download_file(
    file_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    resolved = await loop.run_in_executor(None, reconstruct_file_path, file_path, current_user.id)
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
    return StreamingResponse(file_iterator(file_path), media_type="application/octet-stream", headers=headers)

def construct_ffmpeg_command(input_path: str, output_path: str, params: schemas.ProcessPayload) -> list:
    video_codec = params.videoCodec
    audio_codec = params.audioCodec
    container = params.container
    is_audio_only_output = container in ['mp3', 'flac', 'wav', 'aac', 'ogg']

    if not is_audio_only_output and video_codec != 'copy':
        if container == 'mp4' and video_codec not in ['libx264', 'libx265']:
            video_codec = 'libx264'
        elif container == 'mkv' and video_codec not in ['libx264', 'libx265', 'libaom-av1', 'vp9']:
            video_codec = 'libx264'
        elif container == 'mov' and video_codec not in ['libx264', 'libx265']:
            video_codec = 'libx264'

    if audio_codec != 'copy':
        if container in ['mp4', 'mov'] and audio_codec not in ['aac', 'mp3']:
            audio_codec = 'aac'
        elif container == 'mkv' and audio_codec not in ['aac', 'mp3', 'opus', 'flac']:
            audio_codec = 'aac'
        elif container == 'mp3':
            audio_codec = 'libmp3lame'
        elif container == 'flac':
            audio_codec = 'flac'
        elif container == 'aac':
            audio_codec = 'aac'
        elif container == 'wav':
            audio_codec = 'pcm_s16le'

    command = ["ffmpeg", "-y"]
    input_codec_name = detect_video_codec(input_path)
    if input_codec_name == 'av1':
        command.extend(["-c:v", "av1_cuvid"])
    command.extend(["-analyzeduration", "20M", "-probesize", "20M"])
    command.extend(["-i", input_path])

    if params.startTime > 0:
        command.extend(["-ss", str(params.startTime)])
    if params.endTime < params.totalDuration:
        command.extend(["-to", str(params.endTime)])

    if is_audio_only_output:
        command.append("-vn")
        command.extend(["-map", "0:a?"])
    else:
        command.extend(["-map", "0:v?", "-map", "0:a?"])

    command.extend(["-fflags", "+genpts", "-avoid_negative_ts", "make_zero"])

    if not is_audio_only_output:
        if video_codec != "copy":
            command.extend(["-c:v", video_codec])
            if params.startTime > 0 or params.endTime < params.totalDuration:
                command.extend(["-force_key_frames", "expr:eq(n,0)"])
            if params.videoBitrate:
                command.extend(["-b:v", f"{params.videoBitrate}k"])
            if params.resolution:
                command.extend(["-s", f"{params.resolution.width}x{params.resolution.height}"])
        else:
            command.extend(["-c:v", "copy"])

    if audio_codec != "copy":
        command.extend(["-c:a", audio_codec])
        if params.audioBitrate:
            command.extend(["-b:a", f"{params.audioBitrate}k"])
    else:
        command.extend(["-c:a", "copy"])

    command.append(output_path)
    return command

@router.post("/process", response_model=List[schemas.Task])
async def process_files(
    payload: schemas.ProcessPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    created_tasks = []

    for file_id_str in payload.files:
        try:
            file_id = int(file_id_str)
        except ValueError:
            continue

        db_file = crud.get_file_by_id(db, file_id=file_id)
        if not db_file or db_file.owner_id != current_user.id:
            continue

        input_path = os.path.normpath(db_file.filepath)
        original_filename_base, _ = os.path.splitext(db_file.filename)
        final_display_name = f"{original_filename_base}_processed.{payload.container}"
        final_disk_filename = f"{uuid.uuid4()}.{payload.container}"
        final_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), final_disk_filename))
        temp_output_filename = f"{uuid.uuid4()}.{payload.container}"
        temp_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), temp_output_filename))
        command = construct_ffmpeg_command(input_path, temp_output_path, payload)

        ffmpeg_command_str = " ".join(shlex.quote(c) for c in command)

        task_in = schemas.TaskCreate(
            ffmpeg_command=ffmpeg_command_str,
            source_filename=db_file.filename
        )
        db_task = crud.create_task(db=db, task=task_in, owner_id=current_user.id, output_path=final_output_path)

        task_details = {
            "task_id": db_task.id,
            "command_args": command,
            "total_duration": payload.totalDuration,
            "conn_manager": manager,
            "display_command": ffmpeg_command_str,
            "temp_output_path": temp_output_path,
            "final_output_path": final_output_path,
            "final_display_name": final_display_name,
            "owner_id": current_user.id,
        }
        # 将任务添加到特定用户的队列中
        user_queue = user_task_queues[current_user.id]
        await user_queue.put(task_details)

        created_tasks.append(db_task)

    if not created_tasks:
        raise HTTPException(status_code=404, detail="No valid files found.")

    return created_tasks

@router.delete("/delete-file")
async def delete_user_file(
    filename: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_id = int(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    loop = asyncio.get_running_loop()

    resolved_path = await loop.run_in_executor(
        None, reconstruct_file_path, db_file.filepath, current_user.id
    )

    try:
        await loop.run_in_executor(None, crud.delete_file, db, file_id, resolved_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": f"File {filename} deleted."}

@router.post("/upload", response_model=schemas.FileResponseForFrontend)
async def upload_file(
    file: UploadFile,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        user_upload_directory = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        os.makedirs(user_upload_directory, exist_ok=True)
        file_location = os.path.normpath(os.path.join(user_upload_directory, unique_filename))

        async with aiofiles.open(file_location, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                await out_f.write(chunk)

        loop = asyncio.get_running_loop()
        file_size = await loop.run_in_executor(None, os.path.getsize, file_location)

        try:
            def db_create():
                return crud.create_user_file(
                    db=db,
                    file=schemas.FileCreate(
                        filename=file.filename,
                        filepath=file_location,
                        status="uploaded"
                    ),
                    user_id=current_user.id
                )
            db_file = await loop.run_in_executor(None, db_create)
        except Exception as e:
            # 如果数据库写入失败，删除刚刚上传的文件
            if os.path.exists(file_location):
                os.remove(file_location)
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        # Optionally clear cache when a new file is uploaded
        # invalidate_file_path_cache()

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not upload file: {e}")