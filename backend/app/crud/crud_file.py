# backend/app/crud/crud_file.py
import logging
import time
from pathlib import Path
from typing import cast
from sqlalchemy.orm import Session
from app.models.models import File, ProcessingTask
from app.schemas.file import FileCreate
from app.core.config import invalidate_file_path_cache

logger = logging.getLogger(__name__)


def create_user_file(db: Session, file: FileCreate, user_id: int):
    db_file = File(**file.model_dump(), owner_id=user_id)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


def get_user_files(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(File).filter(File.owner_id == user_id).offset(skip).limit(limit).all()
    )


def get_file_by_id(db: Session, file_id: int):
    return db.query(File).filter(File.id == file_id).first()


def update_file_status(db: Session, file_id: int, new_status: str):
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file:
        db_file.status = cast(str, new_status)
        db.commit()
        db.refresh(db_file)
    return db_file


def delete_file(db: Session, file_id: int, file_path: str | None = None):
    db_file = db.query(File).filter(File.id == file_id).first()
    if not db_file:
        return None
    running_tasks = (
        db.query(ProcessingTask)
        .filter(
            ProcessingTask.source_filename == db_file.filename,
            ProcessingTask.status.in_(["processing", "queued"]),
        )
        .count()
    )

    if running_tasks > 0:
        raise ValueError(
            f"Cannot delete file {file_id} because it has {running_tasks} running tasks associated with it"
        )

    filename = db_file.filename
    path_to_delete = file_path or db_file.filepath
    try:
        db.query(ProcessingTask).filter(
            ProcessingTask.result_file_id == file_id
        ).delete(synchronize_session=False)
        db.query(ProcessingTask).filter(
            ProcessingTask.source_filename == filename
        ).delete(synchronize_session=False)
        db.delete(db_file)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if path_to_delete:
        path = Path(path_to_delete)
        if path.exists():
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning("Delete failed, retrying in 0.5s: %s", e)
                time.sleep(0.5)
                try:
                    path.unlink(missing_ok=True)
                except OSError as e2:
                    logger.error("Error deleting file %s: %s", path_to_delete, e2)

    invalidate_file_path_cache()

    return db_file
