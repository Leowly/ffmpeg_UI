# database.py - Database connection and session management
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. 定义数据库URL
# 优先从环境变量获取，如果没有则使用默认的SQLite地址
SQLALCHEMY_DATABASE_URL = os.environ.get("SQLALCHEMY_DATABASE_URL", "sqlite:///./backend/sql_app.db")

# 2. 创建SQLAlchemy引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    # connect_args 是SQLite专属的配置，为了允许多线程访问
    # 如果是生产环境的PostgreSQL等，可能不需要这个参数
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
)

# 3. 创建数据库会话类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 创建一个Base类，我们的ORM模型将继承这个类
Base = declarative_base()