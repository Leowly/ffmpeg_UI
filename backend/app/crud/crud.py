# backend/app/crud/crud.py

import logging
from typing import cast
from sqlalchemy.orm import Session
import os
import time
from .. import models, schemas
from ..core.security import get_password_hash
from ..core.config import invalidate_file_path_cache


def get_user_by_username(db: Session, username: str):
    """通过用户名查询用户"""
    return db.query(models.User).filter(models.User.username == username).first()


def create_user(db: Session, user: schemas.UserCreate):
    """创建一个新用户，并将其密码哈希后存入数据库"""
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_user_file(db: Session, file: schemas.FileCreate, user_id: int):
    db_file = models.File(**file.model_dump(), owner_id=user_id)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


def get_user_files(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.File)
        .filter(models.File.owner_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_file_by_id(db: Session, file_id: int):
    return db.query(models.File).filter(models.File.id == file_id).first()


def update_file_status(db: Session, file_id: int, new_status: str):
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if db_file:
        db_file.status = cast(str, new_status)
        db.commit()
        db.refresh(db_file)
    return db_file


logger = logging.getLogger(__name__)


def delete_file(db: Session, file_id: int, file_path: str | None = None):
    # 获取要删除的文件信息
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if not db_file:
        return None
    running_tasks = (
        db.query(models.ProcessingTask)
        .filter(
            models.ProcessingTask.source_filename == db_file.filename,
            models.ProcessingTask.status.in_(["processing", "queued"]),
        )
        .count()
    )

    if running_tasks > 0:
        raise ValueError(
            f"Cannot delete file {file_id} because it has {running_tasks} running tasks associated with it"
        )

    filename = db_file.filename
    # 先在数据库中删除相关任务与文件记录，确保数据库状态不产生悬空引用
    path_to_delete = file_path or db_file.filepath
    try:
        db.query(models.ProcessingTask).filter(
            models.ProcessingTask.result_file_id == file_id
        ).delete(synchronize_session=False)
        db.query(models.ProcessingTask).filter(
            models.ProcessingTask.source_filename == filename
        ).delete(synchronize_session=False)
        db.delete(db_file)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # 再尝试物理删除文件，失败时仅记录日志，不回滚数据库状态
    if os.path.exists(path_to_delete):
        try:
            os.remove(path_to_delete)
        except OSError as e:
            logger.warning("Delete failed, retrying in 0.5s: %s", e)
            time.sleep(0.5)
            try:
                os.remove(path_to_delete)
            except OSError as e2:
                logger.error("Error deleting file %s: %s", path_to_delete, e2)

    invalidate_file_path_cache()

    return db_file


def get_user_tasks(db: Session, owner_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.ProcessingTask)
        .filter(models.ProcessingTask.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_task(db: Session, task_id: int):
    """
    根据任务ID从数据库中获取单个任务。
    """
    return (
        db.query(models.ProcessingTask)
        .filter(models.ProcessingTask.id == task_id)
        .first()
    )


def create_task(db: Session, task: schemas.TaskCreate, owner_id: int, output_path: str):
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
    progress: int | None = None,
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
        if progress is not None:
            try:
                db_task.progress = int(progress)
            except Exception:
                pass
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
