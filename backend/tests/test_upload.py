import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import models
from app.core.deps import get_db
from app.core.deps import get_db, get_current_user
from app.core.config import ALLOWED_EXTENSIONS, FILE_SIGNATURES

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_upload.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    return models.User(id=1, username="testuser")


@pytest.fixture(autouse=True)
def setup_database():
    models.Base.metadata.create_all(bind=engine)
    yield
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    return models.User(id=1, username="testuser")


class TestFileSignatureValidation:
    """Test file signature validation logic"""

    def test_validate_file_signature_valid_mp4(self):
        """MP4 file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        mp4_header = b"ftypisom" + b"\x00" * 100
        assert validate_file_signature(mp4_header, ".mp4") is True
        assert validate_file_signature(mp4_header, ".m4v") is True
        assert validate_file_signature(mp4_header, ".mov") is True

    def test_validate_file_signature_valid_mkv(self):
        """MKV file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        mkv_header = b"PK\x03\x04" + b"\x00" * 100
        assert validate_file_signature(mkv_header, ".mkv") is True

    def test_validate_file_signature_valid_png(self):
        """PNG file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert validate_file_signature(png_header, ".png") is True

    def test_validate_file_signature_valid_jpg(self):
        """JPG file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        jpg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert validate_file_signature(jpg_header, ".jpg") is True
        assert validate_file_signature(jpg_header, ".jpeg") is True

    def test_validate_file_signature_valid_webm(self):
        """WebM file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        webm_header = b"\x1aE\xdf\xa3" + b"\x00" * 100
        assert validate_file_signature(webm_header, ".webm") is True

    def test_validate_file_signature_valid_avi(self):
        """AVI file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        avi_header = b"RIFF" + b"xxxx" + b"AVI " + b"\x00" * 100
        assert validate_file_signature(avi_header, ".avi") is True

    def test_validate_file_signature_valid_wav(self):
        """WAV file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        wav_header = b"RIFF" + b"xxxx" + b"WAVE" + b"\x00" * 100
        assert validate_file_signature(wav_header, ".wave") is True

    def test_validate_file_signature_valid_mp3_id3(self):
        """MP3 file with ID3 signature should pass"""
        from app.api.upload import validate_file_signature

        mp3_header = b"ID3" + b"\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
        assert validate_file_signature(mp3_header, ".mp3") is True

    def test_validate_file_signature_valid_mp3_frame(self):
        """MP3 file with frame sync signature should pass"""
        from app.api.upload import validate_file_signature

        assert validate_file_signature(b"\xff\xfb" + b"\x00" * 100, ".mp3") is True
        assert validate_file_signature(b"\xff\xf3" + b"\x00" * 100, ".mp3") is True
        assert validate_file_signature(b"\xff\xf5" + b"\x00" * 100, ".mp3") is True

    def test_validate_file_signature_valid_flac(self):
        """FLAC file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        flac_header = b"fLaC" + b"\x00" * 100
        assert validate_file_signature(flac_header, ".flac") is True

    def test_validate_file_signature_valid_ogg(self):
        """OGG file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        ogg_header = b"OggS" + b"\x00\x02" + b"\x00" * 100
        assert validate_file_signature(ogg_header, ".ogg") is True
        assert validate_file_signature(ogg_header, ".ogv") is True
        assert validate_file_signature(ogg_header, ".opus") is True

    def test_validate_file_signature_valid_wmv(self):
        """WMV/ASF file with correct signature should pass"""
        from app.api.upload import validate_file_signature

        asf_header = b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
        assert validate_file_signature(asf_header, ".wmv") is True

    def test_validate_file_signature_invalid_mismatch(self):
        """File with wrong extension should fail"""
        from app.api.upload import validate_file_signature

        mp4_header = b"ftypisom" + b"\x00" * 100
        assert validate_file_signature(mp4_header, ".mkv") is False
        assert validate_file_signature(mp4_header, ".png") is False
        assert validate_file_signature(mp4_header, ".txt") is False

    def test_validate_file_signature_unknown_signature(self):
        """Unknown signature should pass (pass-through for safety)"""
        from app.api.upload import validate_file_signature

        random_content = b"random data without known signature" + b"\x00" * 100
        assert validate_file_signature(random_content, ".mp4") is False

    def test_validate_file_signature_empty_content(self):
        """Empty content should fail"""
        from app.api.upload import validate_file_signature

        assert validate_file_signature(b"", ".mp4") is False
        assert validate_file_signature(b"\x00", ".mp4") is False


class TestUploadEndpoint:
    """Test upload endpoint with file validation"""

    def test_upload_valid_mp4_file(self, client, tmp_path):
        """Should accept valid MP4 file"""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"ftypisommp42isomavc1" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"
        assert "uid" in data

    def test_upload_valid_png_file(self, client, tmp_path):
        """Should accept valid PNG file"""
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.png", f, "image/png")},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "done"

    def test_upload_valid_jpg_file(self, client, tmp_path):
        """Should accept valid JPG file"""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.jpg", f, "image/jpeg")},
            )

        assert response.status_code == 200

    def test_upload_valid_mp3_file(self, client, tmp_path):
        """Should accept valid MP3 file with ID3"""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"ID3" + b"\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.mp3", f, "audio/mpeg")},
            )

        assert response.status_code == 200

    def test_upload_valid_flac_file(self, client, tmp_path):
        """Should accept valid FLAC file"""
        test_file = tmp_path / "test.flac"
        test_file.write_bytes(b"fLaC" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.flac", f, "audio/flac")},
            )

        assert response.status_code == 200

    def test_upload_valid_wav_file(self, client, tmp_path):
        """Should accept valid WAV file"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.wav", f, "audio/wav")},
            )

        assert response.status_code == 200

    def test_upload_valid_ogg_file(self, client, tmp_path):
        """Should accept valid OGG file"""
        test_file = tmp_path / "test.ogg"
        test_file.write_bytes(b"OggS" + b"\x00\x02" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.ogg", f, "audio/ogg")},
            )

        assert response.status_code == 200

    def test_upload_invalid_extension_txt(self, client, tmp_path):
        """Should reject file with disallowed extension"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello World" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.txt", f, "text/plain")},
            )

        assert response.status_code == 400
        assert "不支持的文件格式" in response.json()["detail"]

    def test_upload_invalid_signature_mp4_extension_wrong_content(
        self, client, tmp_path
    ):
        """Should reject MP4 file with wrong content signature"""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"NOT MP4 CONTENT" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            )

        assert response.status_code == 400
        assert "文件内容与扩展名不匹配" in response.json()["detail"]

    def test_upload_invalid_signature_png_extension_wrong_content(
        self, client, tmp_path
    ):
        """Should reject PNG file with wrong content signature"""
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"JUST RANDOM TEXT" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.png", f, "image/png")},
            )

        assert response.status_code == 400
        assert "文件内容与扩展名不匹配" in response.json()["detail"]

    def test_upload_case_insensitive_extension(self, client, tmp_path):
        """Should accept files regardless of extension case"""
        test_file = tmp_path / "test.MP4"
        test_file.write_bytes(b"ftypisom" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.MP4", f, "video/mp4")},
            )

        assert response.status_code == 200

    def test_upload_mkv_with_ebml_signature(self, client, tmp_path):
        """Should accept valid MKV file"""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"\x1aE\xdf\xa3" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.mkv", f, "video/x-matroska")},
            )

        assert response.status_code == 200

    def test_upload_webm_with_correct_signature(self, client, tmp_path):
        """Should accept valid WebM file"""
        test_file = tmp_path / "test.webm"
        test_file.write_bytes(b"\x1aE\xdf\xa3" + b"\x00" * 100)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.webm", f, "video/webm")},
            )

        assert response.status_code == 200

    def test_upload_empty_file(self, client, tmp_path):
        """Should reject empty file"""
        test_file = tmp_path / "empty.mp4"
        test_file.write_bytes(b"")

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("empty.mp4", f, "video/mp4")},
            )

        assert response.status_code == 400

    def test_upload_very_small_file(self, client, tmp_path):
        """Should handle very small files correctly"""
        test_file = tmp_path / "small.mp4"
        test_file.write_bytes(b"ftyp")  # Partial signature

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("small.mp4", f, "video/mp4")},
            )

        assert response.status_code == 200

    def test_upload_no_file(self, client):
        """Should handle missing file gracefully"""
        response = client.post("/api/upload")
        assert response.status_code in [422, 400]


class TestAllowedExtensions:
    """Test that allowed extensions are properly configured"""

    def test_video_extensions_allowed(self):
        """Video extensions should be in ALLOWED_EXTENSIONS"""
        video_extensions = {
            ".mp4",
            ".m4v",
            ".mov",
            ".mkv",
            ".webm",
            ".avi",
            ".flv",
            ".wmv",
        }
        for ext in video_extensions:
            assert ext in ALLOWED_EXTENSIONS, f"{ext} should be in ALLOWED_EXTENSIONS"

    def test_audio_extensions_allowed(self):
        """Audio extensions should be in ALLOWED_EXTENSIONS"""
        audio_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
        for ext in audio_extensions:
            assert ext in ALLOWED_EXTENSIONS, f"{ext} should be in ALLOWED_EXTENSIONS"

    def test_image_extensions_allowed(self):
        """Image extensions should be in ALLOWED_EXTENSIONS"""
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
        for ext in image_extensions:
            assert ext in ALLOWED_EXTENSIONS, f"{ext} should be in ALLOWED_EXTENSIONS"


class TestFileSignatures:
    """Test that file signatures are properly configured"""

    def test_mp4_signature_exists(self):
        """MP4 signature should be configured"""
        assert b"ftyp" in FILE_SIGNATURES
        assert "mp4" in FILE_SIGNATURES[b"ftyp"]
        assert "m4v" in FILE_SIGNATURES[b"ftyp"]
        assert "mov" in FILE_SIGNATURES[b"ftyp"]

    def test_png_signature_exists(self):
        """PNG signature should be configured"""
        assert b"\x89PNG\r\n\x1a\n" in FILE_SIGNATURES
        assert "png" in FILE_SIGNATURES[b"\x89PNG\r\n\x1a\n"]

    def test_jpg_signature_exists(self):
        """JPG signature should be configured"""
        assert b"\xff\xd8\xff" in FILE_SIGNATURES
        assert "jpg" in FILE_SIGNATURES[b"\xff\xd8\xff"]
        assert "jpeg" in FILE_SIGNATURES[b"\xff\xd8\xff"]

    def test_mp3_signatures_exist(self):
        """MP3 signatures should be configured"""
        assert "mp3" in FILE_SIGNATURES[b"ID3"]
        assert "mp3" in FILE_SIGNATURES[b"\xff\xfb"]
        assert "mp3" in FILE_SIGNATURES[b"\xff\xf3"]
        assert "mp3" in FILE_SIGNATURES[b"\xff\xf5"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
