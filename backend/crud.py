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
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    if db_file:
        db.delete(db_file)
        db.commit()
    return db_file

# --- Task CRUD Operations ---

def get_user_tasks(db: Session, owner_id: int):
    return db.query(models.ProcessingTask).filter(models.ProcessingTask.owner_id == owner_id).all()

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

def update_task(db: Session, task_id: int, status: str, details: str | None = None):
    db_task = db.query(models.ProcessingTask).filter(models.ProcessingTask.id == task_id).first()
    if db_task:
        db_task.status = status
        if details:
            db_task.details = details
        db.commit()
        db.refresh(db_task)
    return db_task