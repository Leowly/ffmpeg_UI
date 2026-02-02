# test_crud.py - CRUD操作单元测试
# 测试覆盖：
# 1. User CRUD 操作
# 2. File CRUD 操作
# 3. Task CRUD 操作
# 注意：使用Mock模拟数据库会话


import pytest
from unittest.mock import MagicMock, patch
from app import crud, models, schemas


class TestUserCRUD:
    """用户CRUD操作测试"""

    def test_get_user_by_username_found(self):
        """测试查找已存在的用户"""
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.username = "testuser"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = crud.get_user_by_username(mock_db, "testuser")

        assert result.username == "testuser"
        mock_db.query.assert_called_once()

    def test_get_user_by_username_not_found(self):
        """测试查找不存在的用户"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = crud.get_user_by_username(mock_db, "nonexistent")

        assert result is None

    @patch("app.crud.crud.get_password_hash")
    def test_create_user(self, mock_hash):
        """测试创建新用户"""
        mock_hash.return_value = "hashed_password"
        mock_db = MagicMock()

        user_create = schemas.UserCreate(username="newuser", password="Password123")

        result = crud.create_user(mock_db, user_create)

        assert result.username == "newuser"
        assert result.hashed_password == "hashed_password"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()


class TestFileCRUD:
    """文件CRUD操作测试"""

    def test_get_user_files(self):
        """测试获取用户文件列表"""
        mock_db = MagicMock()
        mock_files = [MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_files

        result = crud.get_user_files(mock_db, user_id=1)

        assert len(result) == 2
        mock_db.query.assert_called_once()

    def test_get_user_files_with_pagination(self):
        """测试分页获取文件"""
        mock_db = MagicMock()
        mock_files = []
        mock_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_files

        result = crud.get_user_files(mock_db, user_id=1, skip=10, limit=5)

        assert result == mock_files
        # 验证查询链调用
        mock_db.query.return_value.filter.return_value.offset.assert_called_with(10)

    def test_get_file_by_id_found(self):
        """测试按ID查找文件"""
        mock_db = MagicMock()
        mock_file = MagicMock()
        mock_file.id = 1

        mock_db.query.return_value.filter.return_value.first.return_value = mock_file

        result = crud.get_file_by_id(mock_db, file_id=1)

        assert result.id == 1

    def test_get_file_by_id_not_found(self):
        """测试按ID查找不存在的文件"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = crud.get_file_by_id(mock_db, file_id=999)

        assert result is None

    def test_create_user_file(self):
        """测试创建用户文件记录"""
        mock_db = MagicMock()

        file_create = schemas.FileCreate(
            filename="video.mp4", filepath="/path/to/video.mp4"
        )
        result = crud.create_user_file(mock_db, file_create, user_id=1)

        assert result.filename == "video.mp4"
        assert result.owner_id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestTaskCRUD:
    """任务CRUD操作测试"""

    def test_get_user_tasks(self):
        """测试获取用户任务列表"""
        mock_db = MagicMock()
        mock_tasks = [MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_tasks

        result = crud.get_user_tasks(mock_db, owner_id=1)

        assert len(result) == 2

    def test_get_task_found(self):
        """测试按ID查找任务"""
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_task.id = 1

        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        result = crud.get_task(mock_db, task_id=1)

        assert result.id == 1

    def test_get_task_not_found(self):
        """测试按ID查找不存在的任务"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = crud.get_task(mock_db, task_id=999)

        assert result is None

    def test_create_task(self):
        """测试创建任务"""
        mock_db = MagicMock()

        task_create = schemas.TaskCreate(
            ffmpeg_command="-i input.mp4 output.mp4",
            source_filename="input.mp4",
        )
        result = crud.create_task(
            mock_db, task_create, owner_id=1, output_path="/output/output.mp4"
        )

        assert result.ffmpeg_command == "-i input.mp4 output.mp4"
        assert result.owner_id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_update_task_status(self):
        """测试更新任务状态"""
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_task.status = "pending"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        result = crud.update_task(mock_db, task_id=1, status="processing")

        assert result.status == "processing"

    def test_update_task_progress(self):
        """测试更新任务进度"""
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_task.progress = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        result = crud.update_task(mock_db, task_id=1, progress=50)

        assert result.progress == 50

    def test_update_task_multiple_fields(self):
        """测试同时更新多个字段"""
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        crud.update_task(
            mock_db,
            task_id=1,
            status="completed",
            details="Task completed successfully",
            progress=100,
            result_file_id=5,
        )

        assert mock_task.status == "completed"
        assert mock_task.details == "Task completed successfully"
        assert mock_task.progress == 100
        assert mock_task.result_file_id == 5

    def test_delete_task_found(self):
        """测试删除存在的任务"""
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        result = crud.delete_task(mock_db, task_id=1)

        assert result == mock_task
        mock_db.delete.assert_called_once_with(mock_task)
        mock_db.commit.assert_called_once()

    def test_delete_task_not_found(self):
        """测试删除不存在的任务"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = crud.delete_task(mock_db, task_id=999)

        assert result is None
        mock_db.delete.assert_not_called()


class TestDeleteFileWithRunningTasks:
    """删除文件时检查运行中任务的测试"""

    # 注意：由于 delete_file 涉及复杂的 SQLAlchemy 查询链和 os 操作，
    # 这些测试需要集成测试环境。此处只保留简单测试。

    def test_delete_file_not_found(self):
        """测试删除不存在的文件"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = crud.delete_file(mock_db, file_id=999, file_path="/nonexistent")

        assert result is None
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()
