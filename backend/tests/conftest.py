# conftest.py - Pytest configuration and fixtures for API testing

import os
import sys
from pathlib import Path

# 设置测试环境变量 (必须在导入任何 backend 模块之前)
os.environ["PYTEST_RUNNING"] = "1"
os.environ["SECRET_KEY"] = "test_secret_key_for_unit_testing_only_32chars"
os.environ["ENABLE_HARDWARE_ACCELERATION_DETECTION"] = "false"

# 获取项目根目录并添加到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_PATH = PROJECT_ROOT / "backend"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 配置测试数据库
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

import pytest
from fastapi.testclient import TestClient


def pytest_configure(config):
    """Pytest 配置钩子 - 在测试收集之前设置数据库"""
    from app.core.database import Base
    from app.core import database

    # 覆盖数据库引擎
    database.engine = test_engine
    database.SessionLocal = TestSessionLocal

    # 创建测试数据库表
    Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """测试用的数据库会话"""
    from app.core.database import Base

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # 清理并重建表
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """测试客户端"""
    from app.main import app
    from app.core.deps import get_db

    def override_get_db_for_client():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db_for_client

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session):
    """创建测试用户"""
    from app.core.security import get_password_hash
    from app.models import models

    existing_user = (
        db_session.query(models.User)
        .filter(models.User.username == "testuser_e2e")
        .first()
    )

    if existing_user:
        return existing_user

    hashed_password = get_password_hash("TestPassword123!")
    db_user = models.User(
        username="testuser_e2e",
        hashed_password=hashed_password,
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)
    return db_user


@pytest.fixture(scope="function")
def test_user_2(db_session):
    """创建第二个测试用户"""
    from app.core.security import get_password_hash
    from app.models import models

    existing_user = (
        db_session.query(models.User)
        .filter(models.User.username == "testuser_2_e2e")
        .first()
    )

    if existing_user:
        return existing_user

    hashed_password = get_password_hash("AnotherPassword456!")
    db_user = models.User(
        username="testuser_2_e2e",
        hashed_password=hashed_password,
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)
    return db_user


@pytest.fixture
def auth_headers(test_user):
    """生成认证请求头"""
    from app.core.security import create_access_token

    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_2(test_user_2):
    """生成第二个用户的认证请求头"""
    from app.core.security import create_access_token

    token = create_access_token(data={"sub": test_user_2.username})
    return {"Authorization": f"Bearer {token}"}
