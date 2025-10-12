# crud.py - Database Create, Read, Update, Delete operations
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