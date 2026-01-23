# backend/routers/files.py

import asyncio
import json
import os
import subprocess
import uuid
from typing import List, Tuple
import shlex

import aiofiles
from fastapi import (APIRouter, Depends, HTTPException, UploadFile, Request, status)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..dependencies import get_current_user, get_db
from ..processing import manager, user_task_queues
from ..config import (
    UPLOAD_DIRECTORY, 
    reconstruct_file_path, 
    ENABLE_HW_ACCEL_DETECTION,
    MAX_UPLOAD_SIZE,
    ALLOWED_EXTENSIONS
)
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

def detect_hardware_encoder() -> str | None:
    """
    检测可用的硬件编码器类型。
    返回: 'nvidia', 'intel', 'amd', 'mac' 或 None
    """
    if not ENABLE_HW_ACCEL_DETECTION:
        return None

    try:
        # 获取所有可用编码器
        result = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-encoders"],
            capture_output=True,
            text=True
        )
        output = result.stdout

        # 按照优先级检测
        if "h264_nvenc" in output or "hevc_nvenc" in output:
            return "nvidia"
        if "h264_qsv" in output or "hevc_qsv" in output:
            return "intel"
        if "h264_amf" in output or "hevc_amf" in output:
            return "amd"
        if "h264_videotoolbox" in output or "hevc_videotoolbox" in output:
            return "mac"

    except Exception as e:
        print(f"Error detecting hardware acceleration: {e}")

    return None

@router.get("/capabilities", response_model=schemas.SystemCapabilities)
async def get_system_capabilities(
    current_user: models.User = Depends(get_current_user)
):
    hw_type = await asyncio.get_running_loop().run_in_executor(None, detect_hardware_encoder)
    return schemas.SystemCapabilities(
        has_hardware_acceleration=bool(hw_type),
        hardware_type=hw_type
    )

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
    # 1. 基础参数准备
    video_codec = params.videoCodec
    audio_codec = params.audioCodec
    container = params.container
    
    # 仅当用户开启硬件加速开关时，才去检测硬件类型
    hw_type = detect_hardware_encoder() if params.useHardwareAcceleration else None
    # 2. 确定视频编码器 (输出端)
    if params.useHardwareAcceleration and video_codec != 'copy':
        if hw_type == 'nvidia':
            if video_codec == 'libx264': video_codec = 'h264_nvenc'
            elif video_codec == 'libx265': video_codec = 'hevc_nvenc'
            elif video_codec == 'libaom-av1': video_codec = 'av1_nvenc'
        elif hw_type == 'intel':
            if video_codec == 'libx264': video_codec = 'h264_qsv'
            elif video_codec == 'libx265': video_codec = 'hevc_qsv'
        elif hw_type == 'amd':
            if video_codec == 'libx264': video_codec = 'h264_amf'
            elif video_codec == 'libx265': video_codec = 'hevc_amf'
        elif hw_type == 'mac':
            if video_codec == 'libx264': video_codec = 'h264_videotoolbox'
            elif video_codec == 'libx265': video_codec = 'hevc_videotoolbox'

    is_audio_only_output = container in ['mp3', 'flac', 'wav', 'aac', 'ogg']

    # 3. 容器兼容性检查
    if not is_audio_only_output and video_codec != 'copy':
        is_hw_codec = any(k in video_codec for k in ['nvenc', 'qsv', 'amf', 'videotoolbox'])
        if not is_hw_codec:
            if container == 'mp4' and video_codec not in ['libx264', 'libx265', 'libaom-av1']:
                video_codec = 'libx264'
            elif container == 'mkv' and video_codec not in ['libx264', 'libx265', 'libaom-av1', 'vp9']:
                video_codec = 'libx264'
            elif container == 'mov' and video_codec not in ['libx264', 'libx265']:
                video_codec = 'libx264'

    # 音频编码器逻辑
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

    # 4. 构建命令行
    command = ["ffmpeg", "-y"]

    enable_input_hw_accel = False

    if params.useHardwareAcceleration:
        enable_input_hw_accel = True

        if enable_input_hw_accel:
            if hw_type == 'nvidia':
                # 开启 CUDA 硬件加速和零拷贝
                command.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
            elif hw_type == 'intel':
                command.extend(["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"])
            # 其他平台视情况而定

    # 保持大缓冲区，这对 NVDEC 解析 AV1 头信息至关重要
    command.extend(["-analyzeduration", "100M", "-probesize", "100M"])
    command.extend(["-ignore_unknown"])

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

    command.extend(["-fflags", "+genpts"])

    if not is_audio_only_output:
        if video_codec != "copy":
            command.extend(["-c:v", video_codec])

            actual_hw_type = 'cpu'
            if 'nvenc' in video_codec: actual_hw_type = 'nvidia'
            elif 'qsv' in video_codec: actual_hw_type = 'intel'
            elif 'amf' in video_codec: actual_hw_type = 'amd'
            elif 'videotoolbox' in video_codec: actual_hw_type = 'mac'

            preset_map = {
                'nvidia': {'fast': 'p1', 'balanced': 'p4', 'quality': 'p7'},
                'intel': {'fast': 'veryfast', 'balanced': 'medium', 'quality': 'veryslow'},
                'amd': {'fast': 'speed', 'balanced': 'balanced', 'quality': 'quality'},
                'mac': {'fast': 'speed', 'balanced': 'default', 'quality': 'quality'},
                'cpu': {'fast': 'superfast', 'balanced': 'medium', 'quality': 'slow'}
            }
            
            preset_options = preset_map.get(actual_hw_type, preset_map['cpu'])
            actual_preset = preset_options.get(params.preset, preset_options['balanced'])

            if actual_hw_type == 'amd':
                command.extend(["-quality", actual_preset])
            elif actual_hw_type != 'mac': 
                command.extend(["-preset", actual_preset])

            # 处理分辨率 - 智能选择 GPU 滤镜
            if params.resolution:
                if enable_input_hw_accel and actual_hw_type == 'nvidia':
                     # RTX 4050 可以在 GPU 内直接缩放
                     command.extend(["-vf", f"scale_cuda={params.resolution.width}:{params.resolution.height}"])
                elif enable_input_hw_accel and actual_hw_type == 'intel':
                     command.extend(["-vf", f"scale_qsv={params.resolution.width}:{params.resolution.height}"])
                else:
                    command.extend(["-s", f"{params.resolution.width}x{params.resolution.height}"])

            if params.startTime > 0 or params.endTime < params.totalDuration:
                command.extend(["-force_key_frames", "expr:eq(n,0)"])
            if params.videoBitrate:
                command.extend(["-b:v", f"{params.videoBitrate}k"])
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
    request: Request,  # <--- 新增 Request 参数
    file: UploadFile,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. 检查 Content-Length (快速拒绝)
    # 注意：header 中的 content-length 是整个请求体的大小（包含文件名、边界符等），
    # 会略大于文件实际大小，但这作为第一道防线非常有效。
    content_length = request.headers.get('content-length')
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件过大。限制为 {MAX_UPLOAD_SIZE / (1024*1024):.2f} MB"
                )
        except ValueError:
            pass # 如果 header 格式不对，忽略，交给流式检查

    # 2. 检查文件扩展名
    # os.path.splitext 可能无法正确处理文件名中没有点的情况，做个简单判断
    filename = file.filename or ""
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}。仅支持常见的音视频文件。"
        )

    try:
        file_extension = ext # 使用刚才提取的扩展名
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        user_upload_directory = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        os.makedirs(user_upload_directory, exist_ok=True)
        file_location = os.path.normpath(os.path.join(user_upload_directory, unique_filename))

        # 3. 流式写入并实时检查大小 (精准控制)
        # 防止用户伪造 Content-Length header 或者使用分块传输绕过检查
        current_size = 0
        async with aiofiles.open(file_location, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024) # 1MB chunk
                if not chunk:
                    break
                
                current_size += len(chunk)
                if current_size > MAX_UPLOAD_SIZE:
                    # 超过限制：停止写入，关闭文件，删除部分文件，抛出异常
                    await out_f.close() # 显式关闭
                    if os.path.exists(file_location):
                        os.remove(file_location)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件实际大小超过限制 ({MAX_UPLOAD_SIZE / (1024*1024):.2f} MB)"
                    )
                
                await out_f.write(chunk)

        loop = asyncio.get_running_loop()
        file_size = await loop.run_in_executor(None, os.path.getsize, file_location)

        try:
            def db_create():
                return crud.create_user_file(
                    db=db,
                    file=schemas.FileCreate(
                        filename=filename, # 使用原始文件名
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
        # 清理垃圾文件
        if 'file_location' in locals() and os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=500, detail=f"Could not upload file: {str(e)}")