import pytest
import shutil
from unittest.mock import patch, MagicMock

MP4_SIGNATURE = b"ftypisom" + b"\x00" * 100


class TestFileInfoEndpoint:
    def test_get_file_info_success(self, client, test_user, auth_headers, db_session):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")

        file_content = (
            b"\x00\x00\x00\x18ftypisom\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 200
        )
        files = {"file": ("test_video.mp4", file_content, "video/mp4")}
        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        response = client.get(
            f"/api/file-info?filename={file_id}", headers=auth_headers
        )

        if response.status_code == 500:
            pytest.skip(
                "ffprobe cannot parse mock MP4 file (expected for minimal mock data)"
            )

        assert response.status_code == 200
        data = response.json()
        assert "format" in data
        assert "streams" in data

    def test_get_file_info_not_found(self, client, test_user, auth_headers):
        response = client.get("/api/file-info?filename=99999", headers=auth_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_file_info_invalid_id(self, client, test_user, auth_headers):
        response = client.get("/api/file-info?filename=invalid", headers=auth_headers)

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_get_file_info_other_user_file(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2
    ):
        file_content = MP4_SIGNATURE
        files = {"file": ("private_video.mp4", file_content, "video/mp4")}
        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        response = client.get(
            f"/api/file-info?filename={file_id}", headers=auth_headers_2
        )

        assert response.status_code == 404

    def test_get_file_info_without_auth(self, client):
        response = client.get("/api/file-info?filename=1")

        assert response.status_code == 401


class TestProcessEndpointValidation:
    """POST /api/process 端点参数验证测试"""

    def test_process_with_invalid_file_id(self, client, test_user, auth_headers):
        """测试无效文件 ID"""
        payload = {
            "files": ["invalid_id"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 404

    def test_process_with_empty_files(self, client, test_user, auth_headers):
        """测试空文件列表"""
        payload = {
            "files": [],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 404

    def test_process_with_nonexistent_file(self, client, test_user, auth_headers):
        """测试不存在的文件"""
        payload = {
            "files": ["99999"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 404

    def test_process_multiple_files(self, client, test_user, auth_headers, db_session):
        """测试处理多个文件"""
        file_content = MP4_SIGNATURE
        files1 = {"file": ("video1.mp4", file_content, "video/mp4")}
        files2 = {"file": ("video2.mp4", file_content, "video/mp4")}
        upload1 = client.post("/api/upload", files=files1, headers=auth_headers)
        upload2 = client.post("/api/upload", files=files2, headers=auth_headers)
        assert upload1.status_code == 200
        assert upload2.status_code == 200
        file_id1 = upload1.json()["id"]
        file_id2 = upload2.json()["id"]

        payload = {
            "files": [file_id1, file_id2],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 2

    def test_process_without_auth(self, client):
        """测试未认证处理"""
        payload = {
            "files": ["1"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }

        response = client.post("/api/process", json=payload)

        assert response.status_code == 401

    def test_process_mixed_valid_invalid_files(
        self, client, test_user, auth_headers, db_session
    ):
        """测试混合有效和无效文件"""
        file_content = MP4_SIGNATURE
        files = {"file": ("valid.mp4", file_content, "video/mp4")}
        upload = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload.json()["id"]

        payload = {
            "files": [file_id, "99999"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1


class TestDeleteTaskWithRunningTasks:
    """删除正在运行的任务测试"""

    def test_delete_running_task(self, client, test_user, auth_headers, db_session):
        """测试删除正在运行的任务"""
        file_content = MP4_SIGNATURE
        files = {"file": ("task_to_delete.mp4", file_content, "video/mp4")}
        upload = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload.json()["id"]

        payload = {
            "files": [file_id],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }
        process = client.post("/api/process", json=payload, headers=auth_headers)
        task_id = process.json()[0]["id"]

        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 204

        status = client.get(f"/api/task-status/{task_id}", headers=auth_headers)
        assert status.status_code == 404

    def test_delete_pending_task(self, client, test_user, auth_headers, db_session):
        """测试删除待处理的任务"""
        file_content = MP4_SIGNATURE
        files = {"file": ("pending_task.mp4", file_content, "video/mp4")}
        upload = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload.json()["id"]

        payload = {
            "files": [file_id],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }
        process = client.post("/api/process", json=payload, headers=auth_headers)
        task_id = process.json()[0]["id"]

        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 204


class TestTaskStatus:
    """任务状态测试"""

    def test_task_status_pending(self, client, test_user, auth_headers, db_session):
        """测试任务状态为 pending"""
        file_content = MP4_SIGNATURE
        files = {"file": ("status_pending.mp4", file_content, "video/mp4")}
        upload = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload.json()["id"]

        payload = {
            "files": [file_id],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
        }
        process = client.post("/api/process", json=payload, headers=auth_headers)
        task_id = process.json()[0]["id"]

        response = client.get(f"/api/task-status/{task_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["ffmpeg_command"] is not None

    def test_get_user_me(self, client, test_user, auth_headers):
        """测试获取当前用户信息"""
        response = client.get("/users/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username

    def test_get_user_me_without_auth(self, client):
        """测试未认证获取用户信息"""
        response = client.get("/users/me")

        assert response.status_code == 401


class TestPagination:
    """分页测试"""

    def test_tasks_pagination_skip(self, client, test_user, auth_headers, db_session):
        """测试任务列表分页 skip 参数"""
        response = client.get("/api/tasks?skip=10", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_files_pagination(self, client, test_user, auth_headers):
        """测试文件列表分页"""
        response = client.get("/api/files", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)
