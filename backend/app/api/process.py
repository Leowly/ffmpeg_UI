# FFmpeg处理模块

import os
import shlex
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
import logging
from sqlalchemy.orm import Session

from app.crud import crud
from app.models import models
from app.schemas.task import TaskCreate
from app.schemas.system import ProcessPayload
from app.core.deps import get_current_user, get_db
from app.core.config import reconstruct_file_path
from app.services import manager, enqueue_task
from app.services.ffmpeg_builder import construct_ffmpeg_command

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Files"],
)


@router.post("/process")
async def process_files(
    payload: ProcessPayload,
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

        input_path = Path(
            reconstruct_file_path(str(db_file.filepath), current_user.id)
            or db_file.filepath
        )
        original_filename = Path(db_file.filename).stem
        final_display_name = f"{original_filename}_processed.{payload.container}"
        final_disk_filename = f"{uuid.uuid4()}.{payload.container}"
        final_output_path = input_path.parent / final_disk_filename
        temp_output_filename = f"{uuid.uuid4()}.{payload.container}"
        temp_output_path = input_path.parent / temp_output_filename
        command = construct_ffmpeg_command(
            str(input_path), str(temp_output_path), payload
        )

        ffmpeg_command_str = " ".join(shlex.quote(c) for c in command)

        task_in = TaskCreate(
            ffmpeg_command=ffmpeg_command_str, source_filename=db_file.filename
        )
        db_task = crud.create_task(
            db=db,
            task=task_in,
            owner_id=current_user.id,
            output_path=str(final_output_path),
        )

        task_details = {
            "task_id": db_task.id,
            "command_args": command,
            "total_duration": payload.totalDuration,
            "conn_manager": manager,
            "display_command": ffmpeg_command_str,
            "temp_output_path": str(temp_output_path),
            "final_output_path": str(final_output_path),
            "final_display_name": final_display_name,
            "owner_id": current_user.id,
        }
        await enqueue_task(current_user.id, task_details)
        logger.info(
            "Enqueued task_id=%s for user_id=%s",
            db_task.id,
            current_user.id,
        )

        created_tasks.append(db_task)

    if not created_tasks:
        raise HTTPException(status_code=404, detail="No valid files found.")

    return created_tasks
