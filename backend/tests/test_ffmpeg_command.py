import os
import shutil

os.environ["SECRET_KEY"] = "test_secret_key_for_unit_testing_only"
os.environ["ENABLE_HARDWARE_ACCELERATION_DETECTION"] = "false"

import pytest
from unittest.mock import patch, MagicMock
from app import schemas
from app.api.process import construct_ffmpeg_command


def create_payload(
    files=["1"],
    container="mp4",
    videoCodec="libx264",
    audioCodec="aac",
    useHardwareAcceleration=False,
    preset="balanced",
    resolution=None,
    videoBitrate=None,
    audioBitrate=None,
    startTime=0,
    endTime=100,
    totalDuration=100,
):
    return schemas.ProcessPayload(
        files=files,
        container=container,
        startTime=startTime,
        endTime=endTime,
        totalDuration=totalDuration,
        videoCodec=videoCodec,
        audioCodec=audioCodec,
        useHardwareAcceleration=useHardwareAcceleration,
        preset=preset,
        resolution=resolution,
        videoBitrate=videoBitrate,
        audioBitrate=audioBitrate,
    )


class TestContainerCompatibility:
    def test_mp4_with_libx264(self):
        payload = create_payload(container="mp4", videoCodec="libx264")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v libx264" in cmd_str
        assert "-c:a aac" in cmd_str

    def test_mp4_with_libx265(self):
        payload = create_payload(container="mp4", videoCodec="libx265")
        with patch("app.api.process.detect_video_codec", return_value="h265"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v libx265" in cmd_str

    def test_mkv_with_vp9(self):
        payload = create_payload(container="mkv", videoCodec="vp9")
        with patch("app.api.process.detect_video_codec", return_value="vp9"):
            cmd = construct_ffmpeg_command("input.mkv", "output.mkv", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v vp9" in cmd_str

    def test_mov_container(self):
        payload = create_payload(container="mov", videoCodec="libx264")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mov", "output.mov", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v libx264" in cmd_str

    def test_webm_container(self):
        payload = create_payload(
            container="webm", videoCodec="libvpx", audioCodec="libopus"
        )
        with patch("app.api.process.detect_video_codec", return_value="vp8"):
            cmd = construct_ffmpeg_command("input.webm", "output.webm", payload)
        cmd_str = " ".join(cmd)
        assert "output.webm" in cmd_str

    def test_avi_container(self):
        payload = create_payload(
            container="avi", videoCodec="libx264", audioCodec="mp3"
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.avi", "output.avi", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v libx264" in cmd_str

    def test_flv_container(self):
        payload = create_payload(
            container="flv", videoCodec="libx264", audioCodec="mp3"
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.flv", "output.flv", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v libx264" in cmd_str


class TestAudioOnlyContainers:
    def test_mp3_container(self):
        payload = create_payload(container="mp3", audioCodec="libmp3lame")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp3", payload)
        cmd_str = " ".join(cmd)
        assert "-vn" in cmd_str
        assert "-c:a libmp3lame" in cmd_str

    def test_flac_container(self):
        payload = create_payload(container="flac", audioCodec="flac")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.flac", payload)
        cmd_str = " ".join(cmd)
        assert "-vn" in cmd_str
        assert "-c:a flac" in cmd_str

    def test_wav_container(self):
        payload = create_payload(container="wav", audioCodec="pcm_s16le")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.wav", payload)
        cmd_str = " ".join(cmd)
        assert "-vn" in cmd_str
        assert "-c:a pcm_s16le" in cmd_str

    def test_aac_container(self):
        payload = create_payload(container="aac", audioCodec="aac")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.aac", payload)
        cmd_str = " ".join(cmd)
        assert "-vn" in cmd_str
        assert "-c:a aac" in cmd_str

    def test_ogg_container(self):
        payload = create_payload(container="ogg", audioCodec="libvorbis")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.ogg", payload)
        cmd_str = " ".join(cmd)
        assert "-vn" in cmd_str


class TestVideoCodecCopy:
    def test_copy_video_codec(self):
        payload = create_payload(container="mp4", videoCodec="copy", audioCodec="aac")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v copy" in cmd_str
        assert "-c:a aac" in cmd_str


class TestAudioCodecCopy:
    def test_copy_audio_codec(self):
        payload = create_payload(
            container="mp4", videoCodec="libx264", audioCodec="copy"
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-c:v libx264" in cmd_str
        assert "-c:a copy" in cmd_str


class TestTimeRange:
    def test_time_range_trimming(self):
        payload = create_payload(
            container="mp4",
            videoCodec="libx264",
            startTime=10,
            endTime=90,
            totalDuration=100,
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-ss 10" in cmd_str
        assert "-to 90" in cmd_str

    def test_start_time_only(self):
        payload = create_payload(
            container="mp4",
            videoCodec="libx264",
            startTime=10,
            endTime=100,
            totalDuration=100,
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-ss 10" in cmd_str
        assert "-to 90" not in cmd_str


class TestBitrate:
    def test_video_bitrate(self):
        payload = create_payload(
            container="mp4",
            videoCodec="libx264",
            videoBitrate=5000,
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-b:v 5000k" in cmd_str

    def test_audio_bitrate(self):
        payload = create_payload(
            container="mp4",
            videoCodec="libx264",
            audioCodec="aac",
            audioBitrate=192,
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-b:a 192k" in cmd_str


class TestResolution:
    def test_resolution_scale(self):
        res = schemas.Resolution(width=1280, height=720, keepAspectRatio=True)
        payload = create_payload(container="mp4", videoCodec="libx264", resolution=res)
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-s 1280x720" in cmd_str

    def test_resolution_with_hardware(self):
        with patch("app.api.process.detect_hardware_encoder", return_value="nvidia"):
            res = schemas.Resolution(width=1920, height=1080, keepAspectRatio=True)
            payload = create_payload(
                container="mp4",
                videoCodec="libx264",
                useHardwareAcceleration=True,
                resolution=res,
            )
            with patch("app.api.process.detect_video_codec", return_value="h264"):
                cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
            cmd_str = " ".join(cmd)
            assert "scale_cuda=1920:1080" in cmd_str


class TestPresetMapping:
    def test_preset_fast_cpu(self):
        payload = create_payload(
            container="mp4",
            videoCodec="libx264",
            preset="fast",
            useHardwareAcceleration=False,
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-preset superfast" in cmd_str

    def test_preset_quality_cpu(self):
        payload = create_payload(
            container="mp4",
            videoCodec="libx264",
            preset="quality",
            useHardwareAcceleration=False,
        )
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        cmd_str = " ".join(cmd)
        assert "-preset slow" in cmd_str


class TestEdgeCases:
    def test_empty_container(self):
        payload = create_payload(container="")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output", payload)
        assert len(cmd) > 0

    def test_special_chars_in_path(self):
        payload = create_payload(container="mp4")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command(
                "/path/with spaces/file.mp4", "output.mp4", payload
            )
        assert len(cmd) > 0

    def test_output_format(self):
        payload = create_payload(container="mp4")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        assert cmd[0] == "ffmpeg"
        assert cmd[-1] == "output.mp4"

    def test_y_flag_present(self):
        payload = create_payload(container="mp4")
        with patch("app.api.process.detect_video_codec", return_value="h264"):
            cmd = construct_ffmpeg_command("input.mp4", "output.mp4", payload)
        assert "-y" in cmd
