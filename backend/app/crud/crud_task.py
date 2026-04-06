# backend/app/crud/crud_task.py
from sqlalchemy.orm import Session
from app import models
from app.schemas.task import TaskCreate


def get_user_tasks(db: Session, owner_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.ProcessingTask)
        .filter(models.ProcessingTask.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_task(db: Session, task_id: int):
    return (
        db.query(models.ProcessingTask)
        .filter(models.ProcessingTask.id == task_id)
        .first()
    )


def create_task(db: Session, task: TaskCreate, owner_id: int, output_path: str):
    db_task = models.ProcessingTask(
        **task.model_dump(), owner_id=owner_id, output_path=output_path
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def update_task(
    db: Session,
    task_id: int,
    status: str | None = None,
    details: str | None = None,
    result_file_id: int | None = None,
):
    db_task = (
        db.query(models.ProcessingTask)
        .filter(models.ProcessingTask.id == task_id)
        .first()
    )
    if db_task:
        if status:
            db_task.status = status
        if details:
            db_task.details = details
        if result_file_id is not None:
            db_task.result_file_id = result_file_id
        db.commit()
        db.refresh(db_task)
    return db_task


def delete_task(db: Session, task_id: int):
    db_task = (
        db.query(models.ProcessingTask)
        .filter(models.ProcessingTask.id == task_id)
        .first()
    )
    if db_task:
        db.delete(db_task)
        db.commit()
    return db_task
