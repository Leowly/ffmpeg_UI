# 删除模块

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..crud import crud
from ..models import models
from ..core.deps import get_current_user, get_db
from ..core.config import reconstruct_file_path

router = APIRouter(
    tags=["Files"],
)


@router.delete("/delete-file")
async def delete_user_file(
    filename: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
