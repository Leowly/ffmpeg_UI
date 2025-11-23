# backend/routers/tasks.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..dependencies import get_current_user, get_db
from ..processing import terminate_task_process  # 引入刚才写的函数

# 核心修复：移除 prefix="/api"
router = APIRouter(
    tags=["Tasks"],
)

@router.get("/tasks", response_model=List[schemas.Task])
def get_tasks(
    skip: int = 0,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.get_user_tasks(db, owner_id=current_user.id, skip=skip)

@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_task = crud.get_task(db, task_id=task_id)
    if db_task and db_task.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if db_task:
        # 如果任务正在运行，先杀进程
        if db_task.status in ['processing', 'pending']:
            terminate_task_process(task_id)

        crud.delete_task(db, task_id=task_id)

    return

@router.get("/task-status/{taskId}", response_model=schemas.Task)
def get_task_status(
    taskId: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_task = crud.get_task(db, task_id=taskId)
    if not db_task or db_task.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task