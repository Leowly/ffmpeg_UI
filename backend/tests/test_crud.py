"""
CRUD 操作单元测试
测试 crud.py 中的所有函数
"""
import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# 添加项目根目录到 Python 路径
# 确保无论从哪个目录运行测试，都能正确导入backend模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录 (ffmpeg_UI)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
import crud, models, schemas
from database import Base

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def db_session():
    """创建一个测试数据库会话"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # 清理测试数据库文件
        if os.path.exists("./test.db"):
            os.remove("./test.db")

class TestUserCRUD:
    """测试用户相关的 CRUD 操作"""
    
    def test_create_user(self, db_session: Session):
        """测试创建用户"""
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        assert user.username == "testuser"
        assert user.hashed_password != "testpass"  # 应该是哈希值
    
    def test_get_user_by_username(self, db_session: Session):
        """测试根据用户名获取用户"""
        # 先创建一个用户
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        created_user = crud.create_user(db_session, user_data)
        
        # 获取用户
        retrieved_user = crud.get_user_by_username(db_session, "testuser")
        
        assert retrieved_user is not None
        assert retrieved_user.username == "testuser"
        assert retrieved_user.id == created_user.id

class TestFileCRUD:
    """测试文件相关的 CRUD 操作"""
    
    def test_create_user_file(self, db_session: Session):
        """测试创建用户文件"""
        # 先创建一个用户
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        # 创建文件
        file_data = schemas.FileCreate(
            filename="test.mp4",
            filepath="/path/to/test.mp4",
            status="uploaded"
        )
        file = crud.create_user_file(db_session, file_data, user.id)
        
        assert file.filename == "test.mp4"
        assert file.owner_id == user.id
        assert file.status == "uploaded"
    
    def test_get_user_files(self, db_session: Session):
        """测试获取用户文件列表"""
        # 创建用户
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        # 创建两个文件
        file_data1 = schemas.FileCreate(
            filename="test1.mp4",
            filepath="/path/to/test1.mp4",
            status="uploaded"
        )
        file_data2 = schemas.FileCreate(
            filename="test2.mp4",
            filepath="/path/to/test2.mp4",
            status="uploaded"
        )
        crud.create_user_file(db_session, file_data1, user.id)
        crud.create_user_file(db_session, file_data2, user.id)
        
        # 获取用户文件
        files = crud.get_user_files(db_session, user.id)
        
        assert len(files) == 2
        filenames = [f.filename for f in files]
        assert "test1.mp4" in filenames
        assert "test2.mp4" in filenames
    
    def test_get_file_by_id(self, db_session: Session):
        """测试根据ID获取文件"""
        # 创建用户和文件
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        file_data = schemas.FileCreate(
            filename="test.mp4",
            filepath="/path/to/test.mp4",
            status="uploaded"
        )
        created_file = crud.create_user_file(db_session, file_data, user.id)
        
        # 获取文件
        retrieved_file = crud.get_file_by_id(db_session, created_file.id)
        
        assert retrieved_file is not None
        assert retrieved_file.id == created_file.id
        assert retrieved_file.filename == "test.mp4"
    
    def test_update_file_status(self, db_session: Session):
        """测试更新文件状态"""
        # 创建用户和文件
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        file_data = schemas.FileCreate(
            filename="test.mp4",
            filepath="/path/to/test.mp4",
            status="uploaded"
        )
        file = crud.create_user_file(db_session, file_data, user.id)
        
        # 更新状态
        updated_file = crud.update_file_status(db_session, file.id, "processed")
        
        assert updated_file.status == "processed"
        
        # 验证数据库中的实际值
        db_file = crud.get_file_by_id(db_session, file.id)
        assert db_file.status == "processed"
    
    def test_delete_file(self, db_session: Session):
        """测试删除文件"""
        # 创建用户和文件
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        file_data = schemas.FileCreate(
            filename="test.mp4",
            filepath="/path/to/test.mp4",
            status="uploaded"
        )
        file = crud.create_user_file(db_session, file_data, user.id)
        
        # 创建一个关联的任务
        task_data = schemas.TaskCreate(
            ffmpeg_command="ffmpeg -i test.mp4 -c copy output.mp4",
            source_filename="test.mp4"
        )
        task = crud.create_task(db_session, task_data, user.id, "/path/to/output.mp4")
        
        # 测试删除文件（模拟文件存在）
        with patch("os.path.exists", return_value=True), patch("os.remove"):
            deleted_file = crud.delete_file(db_session, file.id, "/path/to/test.mp4")
        
        assert deleted_file is not None
        assert deleted_file.id == file.id
        
        # 文件应该从数据库中删除
        remaining_file = crud.get_file_by_id(db_session, file.id)
        assert remaining_file is None

class TestTaskCRUD:
    """测试任务相关的 CRUD 操作"""
    
    def test_create_task(self, db_session: Session):
        """测试创建任务"""
        # 创建用户
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        # 创建任务
        task_data = schemas.TaskCreate(
            ffmpeg_command="ffmpeg -i input.mp4 -c copy output.mp4",
            source_filename="input.mp4"
        )
        task = crud.create_task(db_session, task_data, user.id, "/path/to/output.mp4")
        
        assert task.ffmpeg_command == "ffmpeg -i input.mp4 -c copy output.mp4"
        assert task.source_filename == "input.mp4"
        assert task.owner_id == user.id
        assert task.output_path == "/path/to/output.mp4"
    
    def test_get_user_tasks(self, db_session: Session):
        """测试获取用户任务列表"""
        # 创建用户
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        # 创建两个任务
        task_data1 = schemas.TaskCreate(
            ffmpeg_command="ffmpeg -i input1.mp4 -c copy output1.mp4",
            source_filename="input1.mp4"
        )
        task_data2 = schemas.TaskCreate(
            ffmpeg_command="ffmpeg -i input2.mp4 -c copy output2.mp4",
            source_filename="input2.mp4"
        )
        crud.create_task(db_session, task_data1, user.id, "/path/to/output1.mp4")
        crud.create_task(db_session, task_data2, user.id, "/path/to/output2.mp4")
        
        # 获取用户任务
        tasks = crud.get_user_tasks(db_session, user.id)
        
        assert len(tasks) == 2
        commands = [t.ffmpeg_command for t in tasks]
        assert "ffmpeg -i input1.mp4 -c copy output1.mp4" in commands
        assert "ffmpeg -i input2.mp4 -c copy output2.mp4" in commands
    
    def test_get_task(self, db_session: Session):
        """测试根据ID获取任务"""
        # 创建用户和任务
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        task_data = schemas.TaskCreate(
            ffmpeg_command="ffmpeg -i input.mp4 -c copy output.mp4",
            source_filename="input.mp4"
        )
        created_task = crud.create_task(db_session, task_data, user.id, "/path/to/output.mp4")
        
        # 获取任务
        retrieved_task = crud.get_task(db_session, created_task.id)
        
        assert retrieved_task is not None
        assert retrieved_task.id == created_task.id
        assert retrieved_task.ffmpeg_command == "ffmpeg -i input.mp4 -c copy output.mp4"
    
    def test_update_task(self, db_session: Session):
        """测试更新任务"""
        # 创建用户和任务
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        task_data = schemas.TaskCreate(
            ffmpeg_command="ffmpeg -i input.mp4 -c copy output.mp4",
            source_filename="input.mp4"
        )
        task = crud.create_task(db_session, task_data, user.id, "/path/to/output.mp4")
        
        # 更新任务
        updated_task = crud.update_task(
            db_session, 
            task.id, 
            status="processing", 
            details="Processing in progress", 
            progress=50,
            result_file_id=1
        )
        
        assert updated_task.status == "processing"
        assert updated_task.details == "Processing in progress"
        assert updated_task.progress == 50
        assert updated_task.result_file_id == 1
        
        # 验证数据库中的实际值
        db_task = crud.get_task(db_session, task.id)
        assert db_task.status == "processing"
    
    def test_delete_task(self, db_session: Session):
        """测试删除任务"""
        # 创建用户和任务
        user_data = schemas.UserCreate(username="testuser", password="testpass")
        user = crud.create_user(db_session, user_data)
        
        task_data = schemas.TaskCreate(
            ffmpeg_command="ffmpeg -i input.mp4 -c copy output.mp4",
            source_filename="input.mp4"
        )
        task = crud.create_task(db_session, task_data, user.id, "/path/to/output.mp4")
        
        # 删除任务
        crud.delete_task(db_session, task.id)
        
        # 任务应该从数据库中删除
        remaining_task = crud.get_task(db_session, task.id)
        assert remaining_task is None

if __name__ == "__main__":
    pytest.main(["-v"])