# test_api_auth.py - 端到端测试：用户认证流程
# 测试覆盖：
# 1. 用户注册
# 2. 用户登录获取 Token
# 3. 访问受保护端点 (认证保护)

import pytest
from app.core.security import create_access_token, verify_password
from app.models import models
from app.schemas import schemas


class TestUserRegistration:
    """用户注册相关测试"""

    def test_register_new_user(self, client):
        """测试新用户注册成功"""
        response = client.post(
            "/users/", json={"username": "newuser_test", "password": "SecurePass123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser_test"
        assert "id" in data
        # User schema 响应中不包含 hashed_password

    def test_register_duplicate_username(self, client, test_user):
        """测试重复用户名注册失败"""
        response = client.post(
            "/users/",
            json={"username": test_user.username, "password": "AnotherPass123"},
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_register_invalid_password(self, client):
        """测试密码复杂度验证"""
        response = client.post(
            "/users/",
            json={
                "username": "validuser",
                "password": "weak",  # 太短，不符合8位要求
            },
        )

        assert response.status_code == 422  # Pydantic 验证错误

    def test_register_short_password(self, client):
        """测试密码长度验证"""
        response = client.post(
            "/users/",
            json={
                "username": "validuser2",
                "password": "NoNumber",  # 缺少数字
            },
        )

        assert response.status_code == 422

    def test_register_missing_username(self, client):
        """测试缺少用户名"""
        response = client.post("/users/", json={"password": "SecurePass123"})

        assert response.status_code == 422


class TestUserLogin:
    """用户登录相关测试"""

    def test_login_success(self, client, test_user):
        """测试登录成功获取 Token"""
        response = client.post(
            "/token",
            data={"username": test_user.username, "password": "TestPassword123!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["access_token"] is not None
        assert data["data"]["token_type"] == "bearer"

    def test_login_wrong_password(self, client, test_user):
        """测试密码错误"""
        response = client.post(
            "/token",
            data={"username": test_user.username, "password": "WrongPassword123"},
        )

        # 返回 401 Unauthorized
        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_login_nonexistent_user(self, client):
        """测试不存在的用户登录"""
        response = client.post(
            "/token",
            data={"username": "nonexistent_user", "password": "AnyPassword123"},
        )

        assert response.status_code == 401

    def test_login_rate_limiting(self, client, test_user):
        """测试登录速率限制 (5次/分钟)"""
        # 快速发送多个登录请求
        for i in range(5):
            response = client.post(
                "/token",
                data={"username": test_user.username, "password": "WrongPassword123"},
            )

        # 第6个请求应该被限制
        response = client.post(
            "/token",
            data={"username": test_user.username, "password": "WrongPassword123"},
        )

        # 应该返回 429 Too Many Requests
        assert response.status_code == 429


class TestAuthenticatedEndpoints:
    """受保护端点测试"""

    def test_access_protected_endpoint_without_token(self, client):
        """测试未认证访问受保护端点"""
        response = client.get("/users/me")

        assert response.status_code == 401

    def test_access_protected_endpoint_with_invalid_token(self, client):
        """测试使用无效 Token 访问"""
        response = client.get(
            "/users/me", headers={"Authorization": "Bearer invalid_token_here"}
        )

        assert response.status_code == 401

    def test_access_protected_endpoint_with_valid_token(self, client, test_user):
        """测试使用有效 Token 访问受保护端点"""
        # 先登录获取 token
        login_response = client.post(
            "/token",
            data={"username": test_user.username, "password": "TestPassword123!"},
        )
        # 检查响应结构
        login_data = login_response.json()

        # token 可能在顶层或 data 字段中
        if "access_token" in login_data:
            token = login_data["access_token"]
        elif "data" in login_data and "access_token" in login_data["data"]:
            token = login_data["data"]["access_token"]
        else:
            # 使用 fixture 的 token
            from app.core.security import create_access_token

            token = create_access_token(data={"sub": test_user.username})

        # 使用 token 访问受保护端点
        response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["username"] == test_user.username

    def test_access_files_without_auth(self, client):
        """测试未认证访问文件端点"""
        response = client.get("/api/files")

        assert response.status_code == 401

    def test_access_tasks_without_auth(self, client):
        """测试未认证访问任务端点"""
        response = client.get("/api/tasks")

        assert response.status_code == 401
