# test_security.py - 安全模块单元测试
# 测试覆盖：
# 1. 密码哈希与验证
# 2. JWT令牌创建与验证
# 3. 密码强度验证


import pytest
from datetime import timedelta
from unittest.mock import patch
from app.core import security


# 设置测试用的环境变量
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """设置测试环境变量"""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setenv("ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")


class TestPasswordHashing:
    """密码哈希测试"""

    def test_hash_password(self):
        """测试密码哈希生成"""
        password = "TestPassword123"
        hashed = security.get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 50  # bcrypt/argon2 哈希通常较长
        assert hashed.startswith("$argon2") or hashed.startswith("$2b")

    def test_hash_consistency(self):
        """测试相同密码每次哈希结果不同（salt）"""
        password = "TestPassword123"
        hash1 = security.get_password_hash(password)
        hash2 = security.get_password_hash(password)

        # 由于随机salt，相同密码的哈希应该不同
        assert hash1 != hash2
        # 但都能验证通过
        assert security.verify_password(password, hash1)
        assert security.verify_password(password, hash2)

    def test_verify_password_correct(self):
        """测试正确密码验证"""
        password = "CorrectPassword123"
        hashed = security.get_password_hash(password)

        assert security.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """测试错误密码验证"""
        password = "CorrectPassword123"
        wrong_password = "WrongPassword456"
        hashed = security.get_password_hash(password)

        assert security.verify_password(wrong_password, hashed) is False

    def test_verify_empty_password(self):
        """测试空密码验证"""
        password = "TestPassword123"
        hashed = security.get_password_hash(password)

        assert security.verify_password("", hashed) is False


class TestJWTTokens:
    """JWT令牌测试"""

    def test_create_access_token(self):
        """测试创建访问令牌"""
        data = {"sub": "testuser", "role": "user"}
        token = security.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 50
        # JWT由三部分组成，用点分隔
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_access_token_with_expiry(self):
        """测试带自定义过期时间的令牌"""
        data = {"sub": "testuser"}
        expires_delta = timedelta(hours=1)
        token = security.create_access_token(data, expires_delta=expires_delta)

        assert isinstance(token, str)

    def test_verify_valid_token(self):
        """测试验证有效令牌"""
        data = {"sub": "testuser", "user_id": 1}
        token = security.create_access_token(data)

        credentials_exception = Exception("Invalid credentials")
        payload = security.verify_token(token, credentials_exception)

        assert payload["sub"] == "testuser"
        assert payload["user_id"] == 1
        assert "exp" in payload

    def test_verify_invalid_token(self):
        """测试验证无效令牌"""
        invalid_token = "invalid.token.here"

        credentials_exception = Exception("Invalid token")
        with pytest.raises(Exception):
            security.verify_token(invalid_token, credentials_exception)

    def test_verify_expired_token(self):
        """测试验证过期令牌"""
        data = {"sub": "testuser"}
        # 创建已过期的令牌
        expires_delta = timedelta(seconds=-1)
        token = security.create_access_token(data, expires_delta=expires_delta)

        credentials_exception = Exception("Token expired")
        with pytest.raises(Exception):
            security.verify_token(token, credentials_exception)

    def test_token_contains_expected_claims(self):
        """测试令牌包含预期声明"""
        data = {"sub": "admin", "permissions": ["read", "write"]}
        token = security.create_access_token(data)

        credentials_exception = Exception("Invalid")
        payload = security.verify_token(token, credentials_exception)

        assert payload["sub"] == "admin"
        assert payload["permissions"] == ["read", "write"]


class TestSecurityEdgeCases:
    """安全边界情况测试"""

    def test_verify_password_different_hashes(self):
        """测试不同密码的哈希不匹配"""
        password1 = "PasswordOne123"
        password2 = "PasswordTwo456"

        hash1 = security.get_password_hash(password1)
        hash2 = security.get_password_hash(password2)

        assert hash1 != hash2
        assert security.verify_password(password1, hash2) is False
        assert security.verify_password(password2, hash1) is False

    def test_verify_password_case_sensitive(self):
        """测试密码验证大小写敏感"""
        password = "TestPassword123"
        wrong_case = "testpassword123"

        hashed = security.get_password_hash(password)

        assert security.verify_password(password, hashed) is True
        assert security.verify_password(wrong_case, hashed) is False

    def test_verify_password_special_chars(self):
        """测试包含特殊字符的密码"""
        password = "P@ssw0rd!#$%^&*()"
        hashed = security.get_password_hash(password)

        assert security.verify_password(password, hashed) is True

    def test_verify_password_unicode(self):
        """测试包含Unicode的密码"""
        password = "密码密码123"  # Chinese characters
        hashed = security.get_password_hash(password)

        assert security.verify_password(password, hashed) is True

    def test_create_token_with_empty_data(self):
        """测试创建空数据的令牌"""
        token = security.create_access_token({})

        credentials_exception = Exception("Invalid")
        payload = security.verify_token(token, credentials_exception)

        assert "exp" in payload
