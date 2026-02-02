# test_schemas.py - Pydantic模型验证单元测试
# 测试覆盖：
# 1. UserCreate 密码验证
# 2. ProcessPayload 参数验证
# 3. 分辨率模型验证
# 4. File/Task 模型构造


import pytest
from app.schemas import schemas


class TestUserCreateSchema:
    """UserCreate 模型验证测试"""

    def test_valid_user_creation(self):
        """测试有效用户数据创建"""
        user = schemas.UserCreate(username="testuser", password="Test1234")
        assert user.username == "testuser"
        assert user.password == "Test1234"

    def test_username_required(self):
        """测试用户名必填"""
        with pytest.raises(Exception):
            schemas.UserCreate(password="Test1234")

    def test_username_min_length(self):
        """测试用户名最小长度"""
        with pytest.raises(Exception):
            schemas.UserCreate(username="", password="Test1234")

    def test_username_max_length(self):
        """测试用户名最大长度（超过50字符）"""
        with pytest.raises(Exception):
            schemas.UserCreate(username="a" * 51, password="Test1234")

    def test_password_required(self):
        """测试密码必填"""
        with pytest.raises(Exception):
            schemas.UserCreate(username="testuser")

    def test_password_min_length(self):
        """测试密码最小长度验证"""
        with pytest.raises(ValueError):
            schemas.UserCreate(username="testuser", password="Ab1")

    def test_password_max_length(self):
        """测试密码最大长度验证"""
        with pytest.raises(ValueError):
            schemas.UserCreate(username="testuser", password="A" * 73)

    def test_password_must_contain_lowercase(self):
        """测试密码必须包含小写字母"""
        with pytest.raises(ValueError, match="必须包含至少一个小写字母"):
            schemas.UserCreate(username="testuser", password="TEST1234")

    def test_password_must_contain_uppercase(self):
        """测试密码必须包含大写字母"""
        with pytest.raises(ValueError, match="必须包含至少一个大写字母"):
            schemas.UserCreate(username="testuser", password="test1234")

    def test_password_must_contain_digit(self):
        """测试密码必须包含数字"""
        with pytest.raises(ValueError, match="必须包含至少一个数字"):
            schemas.UserCreate(username="testuser", password="Testabcd")

    def test_password_valid_complex(self):
        """测试有效复杂密码"""
        user = schemas.UserCreate(username="testuser", password="MySecurePass123")
        assert user.username == "testuser"
        assert len(user.password) >= 8


class TestProcessPayloadSchema:
    """ProcessPayload 模型验证测试"""

    def test_valid_payload(self):
        """测试有效载荷创建"""
        payload = schemas.ProcessPayload(
            files=["1", "2"],
            container="mp4",
            startTime=0,
            endTime=100,
            totalDuration=100,
            videoCodec="libx264",
            audioCodec="aac",
            useHardwareAcceleration=False,
            preset="balanced",
        )
        assert payload.files == ["1", "2"]
        assert payload.container == "mp4"
        assert payload.startTime == 0
        assert payload.endTime == 100

    def test_payload_with_resolution(self):
        """测试带分辨率的载荷"""
        resolution = schemas.Resolution(width=1920, height=1080, keepAspectRatio=True)
        payload = schemas.ProcessPayload(
            files=["1"],
            container="mp4",
            startTime=0,
            endTime=100,
            totalDuration=100,
            videoCodec="libx264",
            audioCodec="aac",
            resolution=resolution,
        )
        assert payload.resolution.width == 1920
        assert payload.resolution.height == 1080

    def test_payload_default_values(self):
        """测试载荷默认值"""
        payload = schemas.ProcessPayload(
            files=["1"],
            container="mp4",
            startTime=0,
            endTime=100,
            totalDuration=100,
            videoCodec="libx264",
            audioCodec="aac",
        )
        assert payload.useHardwareAcceleration is False
        assert payload.preset == "balanced"
        assert payload.videoBitrate is None
        assert payload.audioBitrate is None

    def test_payload_with_bitrate(self):
        """测试带比特率的载荷"""
        payload = schemas.ProcessPayload(
            files=["1"],
            container="mp4",
            startTime=0,
            endTime=100,
            totalDuration=100,
            videoCodec="libx264",
            audioCodec="aac",
            videoBitrate=5000000,
            audioBitrate=192000,
        )
        assert payload.videoBitrate == 5000000
        assert payload.audioBitrate == 192000


class TestResolutionSchema:
    """Resolution 模型验证测试"""

    def test_valid_resolution(self):
        """测试有效分辨率"""
        res = schemas.Resolution(width=1920, height=1080, keepAspectRatio=True)
        assert res.width == 1920
        assert res.height == 1080
        assert res.keepAspectRatio is True

    def test_resolution_defaults(self):
        """测试分辨率默认值（无默认值，必须显式传入）"""
        res = schemas.Resolution(width=1280, height=720, keepAspectRatio=False)
        assert res.keepAspectRatio is False

    def test_invalid_width(self):
        """测试无效宽度（负数）"""
        with pytest.raises(Exception):
            schemas.Resolution(width=-1, height=1080)


class TestFileSchemas:
    """File 相关模型测试"""

    def test_file_create(self):
        """测试 FileCreate 创建"""
        file = schemas.FileCreate(filename="test.mp4", filepath="/path/to/file")
        assert file.filename == "test.mp4"
        assert file.status == "uploaded"  # 默认值

    def test_file_with_custom_status(self):
        """测试自定义状态"""
        file = schemas.FileCreate(
            filename="test.mp4", filepath="/path", status="processing"
        )
        assert file.status == "processing"

    def test_file_response_inner(self):
        """测试 FileResponseInner"""
        response = schemas.FileResponseInner(
            file_id="1", original_name="video.mp4", temp_path="/temp/path"
        )
        assert response.file_id == "1"
        assert response.original_name == "video.mp4"

    def test_file_response_for_frontend(self):
        """测试 FileResponseForFrontend"""
        response = schemas.FileResponseForFrontend(
            uid="1",
            id="1",
            name="video.mp4",
            status="done",
            size=1024,
            response=schemas.FileResponseInner(
                file_id="1", original_name="video.mp4", temp_path="/temp"
            ),
        )
        assert response.uid == "1"
        assert response.size == 1024


class TestTaskSchemas:
    """Task 相关模型测试"""

    def test_task_base(self):
        """测试 TaskBase 创建"""
        task = schemas.TaskBase(ffmpeg_command="-i input.mp4 output.mp4")
        assert task.ffmpeg_command == "-i input.mp4 output.mp4"
        assert task.source_filename is None

    def test_task_create(self):
        """测试 TaskCreate 创建"""
        task = schemas.TaskCreate(
            ffmpeg_command="-i input.mp4 output.mp4", source_filename="input.mp4"
        )
        assert task.ffmpeg_command == "-i input.mp4 output.mp4"
        assert task.source_filename == "input.mp4"


class TestTokenSchemas:
    """Token 相关模型测试"""

    def test_token_response(self):
        """测试 Token 响应模型"""
        token = schemas.Token(access_token="abc123", token_type="bearer")
        assert token.access_token == "abc123"
        assert token.token_type == "bearer"

    def test_token_data(self):
        """测试 TokenData 模型"""
        data = schemas.TokenData(username="testuser")
        assert data.username == "testuser"

    def test_token_data_optional(self):
        """测试 TokenData 可选字段"""
        data = schemas.TokenData()
        assert data.username is None


class TestSystemCapabilitiesSchema:
    """SystemCapabilities 模型测试"""

    def test_capabilities_with_hw(self):
        """测试硬件加速能力检测"""
        caps = schemas.SystemCapabilities(
            has_hardware_acceleration=True, hardware_type="nvidia"
        )
        assert caps.has_hardware_acceleration is True
        assert caps.hardware_type == "nvidia"

    def test_capabilities_without_hw(self):
        """测试无硬件加速"""
        caps = schemas.SystemCapabilities(has_hardware_acceleration=False)
        assert caps.has_hardware_acceleration is False
        assert caps.hardware_type is None


class TestAPIResponseSchema:
    """APIResponse 模型测试"""

    def test_successful_response(self):
        """测试成功响应"""
        response = schemas.APIResponse(success=True, data={"key": "value"})
        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.message is None

    def test_response_with_message(self):
        """测试带消息的响应"""
        response = schemas.APIResponse(success=False, message="Error occurred")
        assert response.success is False
        assert response.message == "Error occurred"

    def test_response_without_data(self):
        """测试无数据的响应"""
        response = schemas.APIResponse(success=True)
        assert response.data is None
