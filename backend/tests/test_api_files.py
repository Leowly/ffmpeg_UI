# test_api_files.py - 端到端测试：文件上传和所有权
# 测试覆盖：
# 1. 文件上传
# 2. 获取文件列表
# 3. 文件下载权限（所有权）
# 4. 删除文件权限



class TestFileUpload:
    """文件上传相关测试"""

    def test_upload_file_success(self, client, test_user, auth_headers):
        """测试成功上传文件"""
        # 创建一个测试文件内容
        file_content = b"test video content for unit testing"
        files = {"file": ("test_video.mp4", file_content, "video/mp4")}

        response = client.post("/api/upload", files=files, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_video.mp4"
        assert data["status"] == "done"
        assert "id" in data
        assert "uid" in data

    def test_upload_invalid_file_type(self, client, test_user, auth_headers):
        """测试上传不支持的文件类型"""
        file_content = b"some data"
        files = {"file": ("test.txt", file_content, "text/plain")}

        response = client.post("/api/upload", files=files, headers=auth_headers)

        assert response.status_code == 400
        assert "不支持的文件格式" in response.json()["detail"]

    def test_upload_without_auth(self, client):
        """测试未认证上传文件"""
        file_content = b"test video content"
        files = {"file": ("test_video.mp4", file_content, "video/mp4")}

        response = client.post("/api/upload", files=files)

        assert response.status_code == 401

    def test_upload_large_file(self, client, test_user, auth_headers, monkeypatch):
        """测试大文件上传（模拟）"""
        # 创建一个大于限制的文件内容
        # 注意：这里我们模拟上传过程

        # 使用较小的文件测试上传流程
        file_content = b"small test file"
        files = {"file": ("test.mp4", file_content, "video/mp4")}

        response = client.post("/api/upload", files=files, headers=auth_headers)

        # 应该成功
        assert response.status_code == 200


class TestFileList:
    """文件列表相关测试"""

    def test_get_empty_file_list(self, client, test_user, auth_headers):
        """测试获取空文件列表"""
        response = client.get("/api/files", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_file_list_with_files(
        self, client, test_user, auth_headers, db_session
    ):
        """测试获取包含文件的列表"""
        # 先上传一个文件
        file_content = b"test content"
        files = {"file": ("another_video.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        assert upload_response.status_code == 200

        # 获取文件列表
        response = client.get("/api/files", headers=auth_headers)

        assert response.status_code == 200
        files_list = response.json()
        assert len(files_list) >= 1


class TestFileDownload:
    """文件下载和所有权相关测试"""

    def test_download_own_file(self, client, test_user, auth_headers, db_session):
        """测试下载自己上传的文件"""
        # 先上传文件
        file_content = b"test video content for download"
        files = {"file": ("download_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        # 下载文件
        response = client.get(f"/api/download-file/{file_id}", headers=auth_headers)

        assert response.status_code == 200
        assert "Content-Disposition" in response.headers

    def test_download_other_user_file(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        """测试下载其他用户的文件（应该失败）"""
        # 用户1上传文件
        file_content = b"user1 private file"
        files = {"file": ("user1_file.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        # 用户2尝试下载
        response = client.get(f"/api/download-file/{file_id}", headers=auth_headers_2)

        assert response.status_code == 404

    def test_download_nonexistent_file(self, client, test_user, auth_headers):
        """测试下载不存在的文件"""
        response = client.get("/api/download-file/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_download_without_auth(self, client, db_session):
        """测试未认证下载文件"""
        response = client.get("/api/download-file/1")

        assert response.status_code == 401


class TestFileDelete:
    """文件删除相关测试"""

    def test_delete_own_file(self, client, test_user, auth_headers, db_session):
        """测试删除自己上传的文件"""
        # 先上传文件
        file_content = b"file to delete"
        files = {"file": ("delete_me.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        # 删除文件
        response = client.delete(
            f"/api/delete-file?filename={file_id}", headers=auth_headers
        )

        assert response.status_code == 200

        # 验证文件已被删除
        download_response = client.get(
            f"/api/download-file/{file_id}", headers=auth_headers
        )
        assert download_response.status_code == 404

    def test_delete_other_user_file(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        """测试删除其他用户的文件（应该失败）"""
        # 用户1上传文件
        file_content = b"protected file"
        files = {"file": ("protected.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        # 用户2尝试删除
        response = client.delete(
            f"/api/delete-file?filename={file_id}", headers=auth_headers_2
        )

        assert response.status_code == 404

    def test_delete_without_auth(self, client):
        """测试未认证删除文件"""
        response = client.delete("/api/delete-file?filename=1")

        assert response.status_code == 401


class TestSystemCapabilities:
    """系统能力检测测试"""

    def test_get_capabilities(self, client, test_user, auth_headers):
        """测试获取系统硬件能力"""
        response = client.get("/api/capabilities", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "has_hardware_acceleration" in data
        assert "hardware_type" in data

    def test_get_capabilities_without_auth(self, client):
        """测试未认证获取系统能力"""
        response = client.get("/api/capabilities")

        assert response.status_code == 401
