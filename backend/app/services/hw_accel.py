# 硬件加速检测模块
# 可直接运行此文件进行硬件支持检测调试

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class HardwareInfo:
    """硬件加速信息"""

    vendor: Optional[str] = None  # 'nvidia', 'intel', 'amd', 'mac', None
    h264_encoder: Optional[str] = None
    hevc_encoder: Optional[str] = None
    av1_encoder: Optional[str] = None
    hwaccel_flag: Optional[str] = None
    hwaccel_output_format: Optional[str] = None

    @property
    def is_available(self) -> bool:
        return self.vendor is not None

    def __str__(self) -> str:
        if not self.is_available:
            return "HardwareInfo: 无可用硬件加速"

        return f"""HardwareInfo:
  厂商: {self.vendor}
  H.264 编码器: {self.h264_encoder or "不支持"}
  HEVC 编码器: {self.hevc_encoder or "不支持"}
  AV1 编码器: {self.av1_encoder or "不支持"}
  HWAccel 标志: {self.hwaccel_flag or "无"}
  HWAccel 输出格式: {self.hwaccel_output_format or "无"}"""


# 编码器映射表
ENCODER_MAP = {
    "nvidia": {
        "h264": "h264_nvenc",
        "hevc": "hevc_nvenc",
        "av1": "av1_nvenc",
        "hwaccel": "cuda",
        "hwaccel_output_format": "cuda",
    },
    "intel": {
        "h264": "h264_qsv",
        "hevc": "hevc_qsv",
        "av1": None,  # Intel QSV AV1 支持有限
        "hwaccel": "qsv",
        "hwaccel_output_format": "qsv",
    },
    "amd": {
        "h264": "h264_amf",
        "hevc": "hevc_amf",
        "av1": "av1_amf",
        "hwaccel": None,  # AMF 通常不需要特殊的 hwaccel 标志
        "hwaccel_output_format": None,
    },
    "mac": {
        "h264": "h264_videotoolbox",
        "hevc": "hevc_videotoolbox",
        "av1": None,  # VideoToolbox AV1 支持有限
        "hwaccel": None,
        "hwaccel_output_format": None,
    },
}


def detect_video_codec(input_path: str) -> str:
    """检测视频文件的视频编码格式"""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=nw=1:nk=1",
            input_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"检测视频编码失败: {e}")
        return ""


def get_ffmpeg_encoders() -> str:
    """获取 FFmpeg 支持的所有编码器列表"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-encoders"], capture_output=True, text=True
        )
        return result.stdout
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg 命令，请确保 FFmpeg 已安装并添加到 PATH")
        return ""
    except Exception as e:
        print(f"获取编码器列表失败: {e}")
        return ""


def get_ffmpeg_hwaccels() -> list[str]:
    """获取 FFmpeg 支持的硬件加速方法"""
    try:
        result = subprocess.run(["ffmpeg", "-hwaccels"], capture_output=True, text=True)
        # 输出格式: 第一行是标题，后面是硬件加速方法
        lines = result.stdout.strip().split("\n")
        if len(lines) > 1:
            return [line.strip() for line in lines[1:] if line.strip()]
        return []
    except Exception as e:
        print(f"获取硬件加速列表失败: {e}")
        return []


def detect_hardware_encoder(enable_detection: bool = True) -> str | None:
    """
    检测可用的硬件编码器类型。

    Args:
        enable_detection: 是否启用检测，默认 True

    Returns:
        'nvidia', 'intel', 'amd', 'mac' 或 None
    """
    if not enable_detection:
        return None

    output = get_ffmpeg_encoders()
    if not output:
        return None

    if "h264_nvenc" in output or "hevc_nvenc" in output:
        return "nvidia"
    if "h264_qsv" in output or "hevc_qsv" in output:
        return "intel"
    if "h264_amf" in output or "hevc_amf" in output:
        return "amd"
    if "h264_videotoolbox" in output or "hevc_videotoolbox" in output:
        return "mac"

    return None


def detect_hardware_info(enable_detection: bool = True) -> HardwareInfo:
    """
    检测详细的硬件加速信息。

    Args:
        enable_detection: 是否启用检测，默认 True

    Returns:
        HardwareInfo 对象，包含详细的硬件加速信息
    """
    info = HardwareInfo()

    if not enable_detection:
        return info

    vendor = detect_hardware_encoder(True)
    if not vendor:
        return info

    info.vendor = vendor
    encoder_config = ENCODER_MAP.get(vendor, {})

    info.h264_encoder = encoder_config.get("h264")
    info.hevc_encoder = encoder_config.get("hevc")
    info.av1_encoder = encoder_config.get("av1")
    info.hwaccel_flag = encoder_config.get("hwaccel")
    info.hwaccel_output_format = encoder_config.get("hwaccel_output_format")

    return info


def print_full_report():
    """打印完整的硬件加速检测报告"""
    print("=" * 60)
    print("FFmpeg 硬件加速检测报告")
    print("=" * 60)

    # 检查 FFmpeg 是否可用
    print("\n[1] 检查 FFmpeg 可用性...")
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        first_line = result.stdout.split("\n")[0]
        print(f"    {first_line}")
    except FileNotFoundError:
        print("    错误: FFmpeg 未安装或不在 PATH 中")
        return
    except Exception as e:
        print(f"    错误: {e}")
        return

    # 获取支持的硬件加速方法
    print("\n[2] 支持的硬件加速方法...")
    hwaccels = get_ffmpeg_hwaccels()
    if hwaccels:
        for hw in hwaccels:
            print(f"    - {hw}")
    else:
        print("    无硬件加速方法支持")

    # 检测硬件编码器
    print("\n[3] 检测硬件编码器...")
    hw_info = detect_hardware_info()
    print(f"    {hw_info}")

    # 列出所有硬件相关编码器
    print("\n[4] 可用的硬件编码器详情...")
    encoders = get_ffmpeg_encoders()

    hw_keywords = ["nvenc", "qsv", "amf", "videotoolbox", "vaapi", "v4l2m2m"]
    found_encoders = []

    for line in encoders.split("\n"):
        for keyword in hw_keywords:
            if keyword in line.lower():
                found_encoders.append(line.strip())
                break

    if found_encoders:
        for encoder in found_encoders[:20]:  # 限制输出行数
            print(f"    {encoder}")
        if len(found_encoders) > 20:
            print(f"    ... 还有 {len(found_encoders) - 20} 个编码器")
    else:
        print("    未找到硬件编码器")

    # 推荐配置
    print("\n[5] 推荐配置...")
    if hw_info.is_available and hw_info.vendor:
        print(f"    推荐使用: {hw_info.vendor.upper()} 硬件加速")
        if hw_info.h264_encoder:
            print(f"    H.264 编码: -c:v {hw_info.h264_encoder}")
        if hw_info.hevc_encoder:
            print(f"    HEVC 编码: -c:v {hw_info.hevc_encoder}")
        if hw_info.hwaccel_flag:
            print(f"    解码加速: -hwaccel {hw_info.hwaccel_flag}")
            if hw_info.hwaccel_output_format:
                print(
                    f"    输出格式: -hwaccel_output_format {hw_info.hwaccel_output_format}"
                )
    else:
        print("    无可用硬件加速，将使用 CPU 软编码")
        print("    推荐编码器: libx264 (H.264) / libx265 (HEVC)")

    print("\n" + "=" * 60)
    print("\n[6] 前端 API 返回参数示例...")
    frontend_payload = {
        "isAvailable": hw_info.is_available,
        "vendor": hw_info.vendor,
        "encoders": {
            "h264": hw_info.h264_encoder,
            "hevc": hw_info.hevc_encoder,
            "av1": hw_info.av1_encoder,
        },
        "hwaccel": {
            "flag": hw_info.hwaccel_flag,
            "outputFormat": hw_info.hwaccel_output_format,
        },
    }
    print(json.dumps(frontend_payload, indent=2, ensure_ascii=False))
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # 检查环境变量配置
    enable_detection = (
        os.environ.get("ENABLE_HARDWARE_ACCELERATION_DETECTION", "true").lower()
        == "true"
    )

    if not enable_detection:
        print("硬件加速检测已通过环境变量禁用")
        print("如需启用，请设置 ENABLE_HARDWARE_ACCELERATION_DETECTION=true")
    else:
        print_full_report()
