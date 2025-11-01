# crud.py - Database Create, Read, Update, Delete operations
from typing import cast
from sqlalchemy.orm import Session

from . import models, schemas
from .security import get_password_hash

# --- User CRUD Operations ---

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

# --- File CRUD Operations ---

def create_user_file(db: Session, file: schemas.FileCreate, user_id: int):
    db_file = models.File(**file.model_dump(), owner_id=user_id)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def get_user_files(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.File).filter(models.File.owner_id == user_id).offset(skip).limit(limit).all()

def get_file_by_id(db: Session, file_id: int):
    return db.query(models.File).filter(models.File.id == file_id).first()

def update_file_status(db: Session, file_id: int, new_status: str):
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if db_file:
        db_file.status = cast(str, new_status)
        db.commit()
        db.refresh(db_file)
    return db_file

def delete_file(db: Session, file_id: int):
    # 获取要删除的文件信息，以便知道其文件名
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if not db_file:
        return None
    
    # 找到所有引用该文件作为结果文件的任务并删除它们
    # 这些是处理该文件后生成的输出文件
    db.query(models.ProcessingTask).filter(
        models.ProcessingTask.result_file_id == file_id
    ).delete(synchronize_session=False)

    # 找到所有使用该文件作为输入的任务并删除它们
    # 通过检查source_filename字段匹配文件名
    db.query(models.ProcessingTask).filter(
        models.ProcessingTask.source_filename == db_file.filename
    ).delete(synchronize_session=False)

    # 删除文件本身
    db.delete(db_file)
    db.commit()
    return db_file

# --- Task CRUD Operations ---

def get_user_tasks(db: Session, owner_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.ProcessingTask).filter(models.ProcessingTask.owner_id == owner_id).offset(skip).limit(limit).all()

def get_task(db: Session, task_id: int):
    """
    根据任务ID从数据库中获取单个任务。
    """
    return db.query(models.ProcessingTask).filter(models.ProcessingTask.id == task_id).first()

def create_task(db: Session, task: schemas.TaskCreate, owner_id: int, output_path: str):
    db_task = models.ProcessingTask(
        **task.model_dump(), 
        owner_id=owner_id,
        output_path=output_path
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def update_task(db: Session, task_id: int, status: str | None = None, details: str | None = None, progress: int | None = None, result_file_id: int | None = None):
    db_task = db.query(models.ProcessingTask).filter(models.ProcessingTask.id == task_id).first()
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
    db_task = db.query(models.ProcessingTask).filter(models.ProcessingTask.id == task_id).first()
    if db_task:
        db.delete(db_task)
        db.commit()
    return db_task