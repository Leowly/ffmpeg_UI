# FFmpeg处理模块

import asyncio
import json
import os
import shlex
import subprocess
import uuid
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..crud import crud
from ..models import models
from ..schemas import schemas
from ..core.deps import get_current_user, get_db
from ..services.processing import manager, user_task_queues
from ..services.hw_accel import detect_hardware_encoder
from ..core.config import reconstruct_file_path

router = APIRouter(
    tags=["Files"],
)


def construct_ffmpeg_command(
    input_path: str, output_path: str, params: schemas.ProcessPayload
) -> list:
    """构建FFmpeg命令"""
    video_codec = params.videoCodec
    audio_codec = params.audioCodec
    container = params.container

    hw_type = detect_hardware_encoder() if params.useHardwareAcceleration else None

    # 确定视频编码器 (输出端)
    if params.useHardwareAcceleration and video_codec != "copy":
        if hw_type == "nvidia":
            if video_codec == "libx264":
                video_codec = "h264_nvenc"
            elif video_codec == "libx265":
                video_codec = "hevc_nvenc"
            elif video_codec == "libaom-av1":
                video_codec = "av1_nvenc"
        elif hw_type == "intel":
            if video_codec == "libx264":
                video_codec = "h264_qsv"
            elif video_codec == "libx265":
                video_codec = "hevc_qsv"
        elif hw_type == "amd":
            if video_codec == "libx264":
                video_codec = "h264_amf"
            elif video_codec == "libx265":
                video_codec = "hevc_amf"
        elif hw_type == "mac":
            if video_codec == "libx264":
                video_codec = "h264_videotoolbox"
            elif video_codec == "libx265":
                video_codec = "hevc_videotoolbox"

    is_audio_only_output = container in ["mp3", "flac", "wav", "aac", "ogg"]

    # 容器兼容性检查
    if not is_audio_only_output and video_codec != "copy":
        is_hw_codec = any(
            k in video_codec for k in ["nvenc", "qsv", "amf", "videotoolbox"]
        )
        if not is_hw_codec:
            if container == "mp4" and video_codec not in [
                "libx264",
                "libx265",
                "libaom-av1",
            ]:
                video_codec = "libx264"
            elif container == "mkv" and video_codec not in [
                "libx264",
                "libx265",
                "libaom-av1",
                "vp9",
            ]:
                video_codec = "libx264"
            elif container == "mov" and video_codec not in ["libx264", "libx265"]:
                video_codec = "libx264"

    # 音频编码器逻辑
    if audio_codec != "copy":
        if container in ["mp4", "mov"] and audio_codec not in ["aac", "mp3"]:
            audio_codec = "aac"
        elif container == "mkv" and audio_codec not in ["aac", "mp3", "opus", "flac"]:
            audio_codec = "aac"
        elif container == "mp3":
            audio_codec = "libmp3lame"
        elif container == "flac":
            audio_codec = "flac"
        elif container == "aac":
            audio_codec = "aac"
        elif container == "wav":
            audio_codec = "pcm_s16le"

    # 构建命令行
    command = ["ffmpeg", "-y"]

    enable_input_hw_accel = False

    if params.useHardwareAcceleration:
        enable_input_hw_accel = True

        if enable_input_hw_accel:
            if hw_type == "nvidia":
                command.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
            elif hw_type == "intel":
                command.extend(["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"])

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

            actual_hw_type = "cpu"
            if "nvenc" in video_codec:
                actual_hw_type = "nvidia"
            elif "qsv" in video_codec:
                actual_hw_type = "intel"
            elif "amf" in video_codec:
                actual_hw_type = "amd"
            elif "videotoolbox" in video_codec:
                actual_hw_type = "mac"

            preset_map = {
                "nvidia": {"fast": "p1", "balanced": "p4", "quality": "p7"},
                "intel": {
                    "fast": "veryfast",
                    "balanced": "medium",
                    "quality": "veryslow",
                },
                "amd": {"fast": "speed", "balanced": "balanced", "quality": "quality"},
                "mac": {"fast": "speed", "balanced": "default", "quality": "quality"},
                "cpu": {"fast": "superfast", "balanced": "medium", "quality": "slow"},
            }

            preset_options = preset_map.get(actual_hw_type, preset_map["cpu"])
            actual_preset = preset_options.get(
                params.preset, preset_options["balanced"]
            )

            if actual_hw_type == "amd":
                command.extend(["-quality", actual_preset])
            elif actual_hw_type != "mac":
                command.extend(["-preset", actual_preset])

            # 处理分辨率
            if params.resolution:
                if enable_input_hw_accel and actual_hw_type == "nvidia":
                    command.extend(
                        [
                            "-vf",
                            f"scale_cuda={params.resolution.width}:{params.resolution.height}",
                        ]
                    )
                elif enable_input_hw_accel and actual_hw_type == "intel":
                    command.extend(
                        [
                            "-vf",
                            f"scale_qsv={params.resolution.width}:{params.resolution.height}",
                        ]
                    )
                else:
                    command.extend(
                        ["-s", f"{params.resolution.width}x{params.resolution.height}"]
                    )

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
    db: Session = Depends(get_db),
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
        final_output_path = os.path.normpath(
            os.path.join(os.path.dirname(input_path), final_disk_filename)
        )
        temp_output_filename = f"{uuid.uuid4()}.{payload.container}"
        temp_output_path = os.path.normpath(
            os.path.join(os.path.dirname(input_path), temp_output_filename)
        )
        command = construct_ffmpeg_command(input_path, temp_output_path, payload)

        ffmpeg_command_str = " ".join(shlex.quote(c) for c in command)

        task_in = schemas.TaskCreate(
            ffmpeg_command=ffmpeg_command_str, source_filename=db_file.filename
        )
        db_task = crud.create_task(
            db=db, task=task_in, owner_id=current_user.id, output_path=final_output_path
        )

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
        user_queue = user_task_queues[current_user.id]
        await user_queue.put(task_details)

        created_tasks.append(db_task)

    if not created_tasks:
        raise HTTPException(status_code=404, detail="No valid files found.")

    return created_tasks
