from app.schemas.system import ProcessPayload
from app.services.hw_accel import detect_hardware_encoder


def construct_ffmpeg_command(
    input_path: str, output_path: str, params: ProcessPayload
) -> list:
    video_codec = params.videoCodec
    audio_codec = params.audioCodec
    container = params.container

    hw_type = detect_hardware_encoder() if params.useHardwareAcceleration else None

    if params.useHardwareAcceleration and video_codec != "copy":
        if hw_type == "nvidia":
            if video_codec == "libx264":
                video_codec = "h264_nvenc"
            elif video_codec == "libx265":
                video_codec = "hevc_nvenc"
            elif video_codec == "libaom-av1":
                video_codec = "av1_nvenc"
        elif hw_type == "intel":
            if video_codec == "libx264":
                video_codec = "h264_qsv"
            elif video_codec == "libx265":
                video_codec = "hevc_qsv"
        elif hw_type == "amd":
            if video_codec == "libx264":
                video_codec = "h264_amf"
            elif video_codec == "libx265":
                video_codec = "hevc_amf"
        elif hw_type == "mac":
            if video_codec == "libx264":
                video_codec = "h264_videotoolbox"
            elif video_codec == "libx265":
                video_codec = "hevc_videotoolbox"
        elif hw_type == "vaapi":
            if video_codec == "libx264":
                video_codec = "h264_vaapi"
            elif video_codec == "libx265":
                video_codec = "hevc_vaapi"
            elif video_codec == "libaom-av1":
                video_codec = "av1_vaapi"

    is_audio_only_output = container in ["mp3", "flac", "wav", "aac", "ogg"]

    if not is_audio_only_output and video_codec != "copy":
        is_hw_codec = any(
            k in video_codec for k in ["nvenc", "qsv", "amf", "videotoolbox", "vaapi"]
        )
        if not is_hw_codec:
            if container == "mp4" and video_codec not in [
                "libx264",
                "libx265",
                "libaom-av1",
            ]:
                video_codec = "libx264"
            elif container == "mkv" and video_codec not in [
                "libx264",
                "libx265",
                "libaom-av1",
                "vp9",
            ]:
                video_codec = "libx264"
            elif container == "mov" and video_codec not in ["libx264", "libx265"]:
                video_codec = "libx264"

    if audio_codec != "copy":
        if container in ["mp4", "mov"] and audio_codec not in ["aac", "mp3"]:
            audio_codec = "aac"
        elif container == "mkv" and audio_codec not in ["aac", "mp3", "opus", "flac"]:
            audio_codec = "aac"
        elif container == "mp3":
            audio_codec = "libmp3lame"
        elif container == "flac":
            audio_codec = "flac"
        elif container == "aac":
            audio_codec = "aac"
        elif container == "wav":
            audio_codec = "pcm_s16le"

    command = ["ffmpeg", "-y"]

    enable_input_hw_accel = False

    if params.useHardwareAcceleration:
        enable_input_hw_accel = True

        if enable_input_hw_accel:
            if hw_type == "nvidia":
                command.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
            elif hw_type == "intel":
                command.extend(["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"])
            elif hw_type == "vaapi":
                command.extend(["-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"])

    command.extend(["-analyzeduration", "100M", "-probesize", "100M"])
    command.extend(["-ignore_unknown"])

    command.extend(["-i", input_path])

    if params.startTime > 0:
        command.extend(["-ss", str(params.startTime)])
    if params.endTime < params.totalDuration:
        command.extend(["-to", str(params.endTime)])

    if is_audio_only_output:
        command.append("-vn")
        command.extend(["-map", "0:a?"])
    else:
        command.extend(["-map", "0:v?", "-map", "0:a?"])

    command.extend(["-fflags", "+genpts"])

    if not is_audio_only_output:
        if video_codec != "copy":
            command.extend(["-c:v", video_codec])

            actual_hw_type = "cpu"
            if "nvenc" in video_codec:
                actual_hw_type = "nvidia"
            elif "qsv" in video_codec:
                actual_hw_type = "intel"
            elif "amf" in video_codec:
                actual_hw_type = "amd"
            elif "videotoolbox" in video_codec:
                actual_hw_type = "mac"
            elif "vaapi" in video_codec:
                actual_hw_type = "vaapi"

            preset_map = {
                "nvidia": {"fast": "p1", "balanced": "p4", "quality": "p7"},
                "intel": {
                    "fast": "veryfast",
                    "balanced": "medium",
                    "quality": "veryslow",
                },
                "amd": {"fast": "speed", "balanced": "balanced", "quality": "quality"},
                "mac": {"fast": "speed", "balanced": "default", "quality": "quality"},
                "vaapi": {"fast": "fast", "balanced": "medium", "quality": "slow"},
                "cpu": {"fast": "superfast", "balanced": "medium", "quality": "slow"},
            }

            preset_options = preset_map.get(actual_hw_type, preset_map["cpu"])
            actual_preset = preset_options.get(
                params.preset, preset_options["balanced"]
            )

            if actual_hw_type == "amd":
                command.extend(["-quality", actual_preset])
            elif actual_hw_type != "mac":
                command.extend(["-preset", actual_preset])

            if params.resolution:
                if enable_input_hw_accel and actual_hw_type == "nvidia":
                    command.extend(
                        [
                            "-vf",
                            f"scale_cuda={params.resolution.width}:{params.resolution.height}",
                        ]
                    )
                elif enable_input_hw_accel and actual_hw_type == "intel":
                    command.extend(
                        [
                            "-vf",
                            f"scale_qsv={params.resolution.width}:{params.resolution.height}",
                        ]
                    )
                else:
                    command.extend(
                        ["-s", f"{params.resolution.width}x{params.resolution.height}"]
                    )

            if params.startTime > 0 or params.endTime < params.totalDuration:
                command.extend(["-force_key_frames", "expr:eq(n,0)"])
            if params.videoBitrate:
                command.extend(["-b:v", f"{params.videoBitrate}k"])
        else:
            command.extend(["-c:v", "copy"])

    if audio_codec != "copy":
        command.extend(["-c:a", audio_codec])
        if params.audioBitrate:
            command.extend(["-b:a", f"{params.audioBitrate}k"])
    else:
        command.extend(["-c:a", "copy"])

    command.append(output_path)
    return command
