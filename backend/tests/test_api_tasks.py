# test_api_tasks.py - 端到端测试：任务处理流程
# 测试覆盖：
# 1. 创建处理任务
# 2. 获取任务列表
# 3. 获取任务状态
# 4. 删除任务
# 5. 任务所有权验证



class TestTaskCreation:
    """任务创建相关测试"""

    def test_create_processing_task(self, client, test_user, auth_headers, db_session):
        """测试创建处理任务"""
        # 先上传一个文件
        file_content = b"fake video content for task testing"
        files = {"file": ("task_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        # 创建处理任务
        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) >= 1
        assert tasks[0]["ffmpeg_command"] is not None

    def test_create_task_with_invalid_file(self, client, test_user, auth_headers):
        """测试使用无效文件创建任务"""
        payload = {
            "files": ["99999"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        # 应该返回 404 因为没有有效文件
        assert response.status_code == 404

    def test_create_task_without_auth(self, client):
        """测试未认证创建任务"""
        payload = {
            "files": ["1"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        response = client.post("/api/process", json=payload)

        assert response.status_code == 401


class TestTaskList:
    """任务列表相关测试"""

    def test_get_empty_task_list(self, client, test_user, auth_headers):
        """测试获取空任务列表"""
        response = client.get("/api/tasks", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_task_list_with_tasks(
        self, client, test_user, auth_headers, db_session
    ):
        """测试获取包含任务的任务列表"""
        # 先上传文件并创建任务
        file_content = b"content for task list test"
        files = {"file": ("tasklist_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        # 创建任务
        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        assert process_response.status_code == 200

        # 获取任务列表
        response = client.get("/api/tasks", headers=auth_headers)

        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) >= 1

    def test_get_task_list_pagination(self, client, test_user, auth_headers):
        """测试任务列表分页"""
        response = client.get("/api/tasks?skip=0", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestTaskStatus:
    """任务状态相关测试"""

    def test_get_task_status(self, client, test_user, auth_headers, db_session):
        """测试获取任务状态"""
        # 创建任务
        file_content = b"content for status test"
        files = {"file": ("status_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        # 获取任务状态
        response = client.get(f"/api/task-status/{task_id}", headers=auth_headers)

        assert response.status_code == 200
        task = response.json()
        assert task["id"] == task_id
        assert task["status"] in ["pending", "processing", "completed", "failed"]

    def test_get_other_user_task_status(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        """测试获取其他用户的任务状态（应该失败）"""
        # 用户1创建任务
        file_content = b"user1 task"
        files = {"file": ("u1_task.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        # 用户2尝试获取状态
        response = client.get(f"/api/task-status/{task_id}", headers=auth_headers_2)

        assert response.status_code == 404

    def test_get_nonexistent_task_status(self, client, test_user, auth_headers):
        """测试获取不存在的任务状态"""
        response = client.get("/api/task-status/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_get_task_status_without_auth(self, client):
        """测试未认证获取任务状态"""
        response = client.get("/api/task-status/1")

        assert response.status_code == 401


class TestTaskDeletion:
    """任务删除相关测试"""

    def test_delete_task(self, client, test_user, auth_headers, db_session):
        """测试删除任务"""
        # 创建任务
        file_content = b"content for delete test"
        files = {"file": ("delete_task_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        # 删除任务
        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 204

        # 验证任务已被删除
        status_response = client.get(
            f"/api/task-status/{task_id}", headers=auth_headers
        )
        assert status_response.status_code == 404

    def test_delete_other_user_task(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        """测试删除其他用户的任务（应该失败）"""
        # 用户1创建任务
        file_content = b"protected task"
        files = {"file": ("protected_task.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        # 用户2尝试删除
        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers_2)

        assert response.status_code == 403

    def test_delete_nonexistent_task(self, client, test_user, auth_headers):
        """测试删除不存在的任务"""
        response = client.delete("/api/tasks/99999", headers=auth_headers)

        # 应该静默成功（返回 204）
        assert response.status_code == 204

    def test_delete_task_without_auth(self, client):
        """测试未认证删除任务"""
        response = client.delete("/api/tasks/1")

        assert response.status_code == 401
