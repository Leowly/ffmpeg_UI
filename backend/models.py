# models.py - SQLAlchemy database models
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    files = relationship("File", back_populates="owner")
    tasks = relationship("ProcessingTask", back_populates="owner") # Add relationship to tasks

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    filepath = Column(String, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="uploaded") # e.g., uploaded, processing, completed, failed

    owner = relationship("User", back_populates="files")

class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    # 使用 text 类型以存储可能很长的 ffmpeg 命令
    ffmpeg_command = Column(Text, nullable=False)
    source_filename = Column(String, nullable=True, default="") # 用于存储源文件名，并设置默认值
    output_path = Column(String, nullable=True) # 用于存储输出文件路径
    progress = Column(Integer, default=0) # 0-100 百分比进度
    # pending, processing, completed, failed
    status = Column(String, default="pending", index=True)
    details = Column(Text, nullable=True) # 用于存储日志或错误信息
    owner_id = Column(Integer, ForeignKey("users.id"))

    # 与结果文件的关联
    result_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    result_file = relationship("File")

    owner = relationship("User", back_populates="tasks")