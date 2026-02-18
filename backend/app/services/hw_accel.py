# 硬件加速检测模块

import json
import os
import platform
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass
class GPUDevice:
    name: str
    vendor: str


@dataclass
class HardwareInfo:
    isAvailable: bool = False
    vendor: Optional[str] = None
    h264_encoder: Optional[str] = None
    hevc_encoder: Optional[str] = None
    av1_encoder: Optional[str] = None
    hwaccel_flag: Optional[str] = None
    hwaccel_output_format: Optional[str] = None
    gpu_name: Optional[str] = None

    def to_api_response(self) -> dict:
        return {
            "isAvailable": self.isAvailable,
            "vendor": self.vendor,
            "gpuName": self.gpu_name,
            "encoders": {
                "h264": self.h264_encoder,
                "hevc": self.hevc_encoder,
                "av1": self.av1_encoder,
            },
            "hwaccel": {
                "flag": self.hwaccel_flag,
                "outputFormat": self.hwaccel_output_format,
            },
        }


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
        "av1": None,
        "hwaccel": "qsv",
        "hwaccel_output_format": "qsv",
    },
    "amd": {
        "h264": "h264_amf",
        "hevc": "hevc_amf",
        "av1": "av1_amf",
        "hwaccel": None,
        "hwaccel_output_format": None,
    },
    "apple": {
        "h264": "h264_videotoolbox",
        "hevc": "hevc_videotoolbox",
        "av1": None,
        "hwaccel": None,
        "hwaccel_output_format": None,
    },
    "vaapi": {
        "h264": "h264_vaapi",
        "hevc": "hevc_vaapi",
        "av1": "av1_vaapi",
        "hwaccel": "vaapi",
        "hwaccel_output_format": "vaapi",
    },
}


def _detect_nvidia_smi() -> GPUDevice | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "GPU" in line:
                    name = line.split(":")[1].split("(")[0].strip()
                    return GPUDevice(name=name, vendor="nvidia")
    except Exception:
        pass
    return None


def _detect_gpus_windows() -> list[GPUDevice]:
    gpus = []

    nvidia = _detect_nvidia_smi()
    if nvidia:
        gpus.append(nvidia)

    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:
            name = line.strip()
            if not name:
                continue
            name_lower = name.lower()
            if "nvidia" in name_lower:
                if not any(g.vendor == "nvidia" for g in gpus):
                    gpus.append(GPUDevice(name=name, vendor="nvidia"))
            elif "intel" in name_lower and (
                "iris" in name_lower
                or "uhd" in name_lower
                or "xe" in name_lower
                or "graphics" in name_lower
            ):
                gpus.append(GPUDevice(name=name, vendor="intel"))
            elif "amd" in name_lower or "radeon" in name_lower:
                gpus.append(GPUDevice(name=name, vendor="amd"))
    except Exception:
        pass
    return gpus


def _detect_gpus_windows_no_nvidia() -> list[GPUDevice]:
    gpus = []
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:
            name = line.strip()
            if not name:
                continue
            name_lower = name.lower()
            if "intel" in name_lower and (
                "iris" in name_lower
                or "uhd" in name_lower
                or "xe" in name_lower
                or "graphics" in name_lower
            ):
                gpus.append(GPUDevice(name=name, vendor="intel"))
            elif "amd" in name_lower or "radeon" in name_lower:
                gpus.append(GPUDevice(name=name, vendor="amd"))
    except Exception:
        pass
    return gpus


def _detect_gpus_linux() -> list[GPUDevice]:
    gpus = []
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.split("\n"):
            line_lower = line.lower()
            if "vga" in line_lower or "3d" in line_lower or "display" in line_lower:
                if "nvidia" in line_lower:
                    gpus.append(
                        GPUDevice(name=line.split(":")[-1].strip(), vendor="nvidia")
                    )
                elif "intel" in line_lower:
                    gpus.append(
                        GPUDevice(name=line.split(":")[-1].strip(), vendor="intel")
                    )
                elif "amd" in line_lower or "radeon" in line_lower:
                    gpus.append(
                        GPUDevice(name=line.split(":")[-1].strip(), vendor="amd")
                    )
    except Exception:
        pass

    if not gpus:
        try:
            for entry in os.listdir("/sys/class/drm"):
                device_path = f"/sys/class/drm/{entry}/device/vendor"
                if os.path.exists(device_path):
                    with open(device_path) as f:
                        vendor_id = f.read().strip()
                    vendor_id = vendor_id.replace("0x", "")
                    if vendor_id == "10de":
                        gpus.append(GPUDevice(name=entry, vendor="nvidia"))
                    elif vendor_id == "8086":
                        gpus.append(GPUDevice(name=entry, vendor="intel"))
                    elif vendor_id == "1002":
                        gpus.append(GPUDevice(name=entry, vendor="amd"))
        except Exception:
            pass

    if not any(g.vendor == "nvidia" for g in gpus):
        vaapi_device = _detect_vaapi_device()
        if vaapi_device:
            gpus.append(vaapi_device)

    return gpus


def _detect_vaapi_device() -> GPUDevice | None:
    if not os.path.exists("/dev/dri"):
        return None
    try:
        for entry in os.listdir("/dev/dri"):
            if entry.startswith("renderD"):
                try:
                    result = subprocess.run(
                        ["vainfo"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split("\n"):
                            if "VAProfile" in line:
                                name = "VAAPI Device"
                                if "Intel" in result.stdout:
                                    name = "Intel VAAPI"
                                elif (
                                    "AMD" in result.stdout or "Radeon" in result.stdout
                                ):
                                    name = "AMD VAAPI"
                                return GPUDevice(name=name, vendor="vaapi")
                except Exception:
                    pass
                break
    except Exception:
        pass
    return None


def _detect_gpus_macos() -> list[GPUDevice]:
    gpus = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
        )
        output = result.stdout
        for line in output.split("\n"):
            if "Chipset Model:" in line:
                name = line.split(":")[-1].strip()
                name_lower = name.lower()
                if (
                    "apple" in name_lower
                    or "m1" in name_lower
                    or "m2" in name_lower
                    or "m3" in name_lower
                    or "m4" in name_lower
                ):
                    gpus.append(GPUDevice(name=name, vendor="apple"))
                elif "nvidia" in name_lower:
                    gpus.append(GPUDevice(name=name, vendor="nvidia"))
                elif "amd" in name_lower or "radeon" in name_lower:
                    gpus.append(GPUDevice(name=name, vendor="amd"))
                elif "intel" in name_lower:
                    gpus.append(GPUDevice(name=name, vendor="intel"))
    except Exception:
        pass
    return gpus


_cached_gpus: list[GPUDevice] | None = None


@lru_cache(maxsize=1)
def _get_ffmpeg_encoders_cache() -> str:
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-encoders"],
            capture_output=True,
            text=True,
        )
        return result.stdout
    except Exception:
        return ""


def detect_gpus() -> list[GPUDevice]:
    global _cached_gpus
    if _cached_gpus is not None:
        return _cached_gpus

    system = platform.system()
    if system == "Windows":
        _cached_gpus = _detect_gpus_windows()
    elif system == "Linux":
        _cached_gpus = _detect_gpus_linux()
    elif system == "Darwin":
        _cached_gpus = _detect_gpus_macos()
    else:
        _cached_gpus = []
    return _cached_gpus


def detect_gpus_fast() -> list[GPUDevice]:
    global _cached_gpus
    if _cached_gpus is not None:
        return _cached_gpus

    if platform.system() == "Windows":
        nvidia = _detect_nvidia_smi()
        if nvidia:
            _cached_gpus = [nvidia]
            return _cached_gpus

        _cached_gpus = _detect_gpus_windows_no_nvidia()
        return _cached_gpus

    return detect_gpus()


def check_ffmpeg_encoder(encoder: str) -> bool:
    if not encoder:
        return False
    return encoder in _get_ffmpeg_encoders_cache()


def detect_hardware_info(enable_detection: bool = True) -> HardwareInfo:
    if not enable_detection:
        return HardwareInfo()

    gpus = detect_gpus_fast()
    if not gpus:
        return HardwareInfo()

    priority = ["nvidia", "amd", "intel", "vaapi", "apple"]
    gpus_sorted = sorted(
        gpus,
        key=lambda g: priority.index(g.vendor) if g.vendor in priority else 999,
    )

    for gpu in gpus_sorted:
        config = ENCODER_MAP.get(gpu.vendor)
        if not config:
            continue

        h264 = config.get("h264")
        hevc = config.get("hevc")
        av1 = config.get("av1")

        if h264 and check_ffmpeg_encoder(h264):
            return HardwareInfo(
                isAvailable=True,
                vendor=gpu.vendor,
                h264_encoder=h264,
                hevc_encoder=hevc if hevc and check_ffmpeg_encoder(hevc) else None,
                av1_encoder=av1 if av1 and check_ffmpeg_encoder(av1) else None,
                hwaccel_flag=config.get("hwaccel"),
                hwaccel_output_format=config.get("hwaccel_output_format"),
                gpu_name=gpu.name,
            )

    return HardwareInfo()


def detect_hardware_encoder(enable_detection: bool = True) -> str | None:
    info = detect_hardware_info(enable_detection)
    return info.vendor


def get_ffmpeg_hwaccels() -> list[str]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hwaccels"],
            capture_output=True,
            text=True,
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) > 1:
            return [line.strip() for line in lines[1:] if line.strip()]
        return []
    except Exception:
        return []


def print_full_report():
    print("=" * 60)
    print("FFmpeg 硬件加速检测报告")
    print("=" * 60)

    print("\n[1] 系统检测到的 GPU 硬件...")
    gpus = detect_gpus()
    if gpus:
        for gpu in gpus:
            print(f"    [{gpu.vendor.upper()}] {gpu.name}")
    else:
        print("    未检测到 GPU")

    print("\n[2] FFmpeg 版本...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
        )
        print(f"    {result.stdout.split(chr(10))[0]}")
    except FileNotFoundError:
        print("    错误: FFmpeg 未安装或不在 PATH 中")
        return
    except Exception as e:
        print(f"    错误: {e}")
        return

    print("\n[3] FFmpeg 编译支持的硬件加速方法...")
    hwaccels = get_ffmpeg_hwaccels()
    if hwaccels:
        for hw in hwaccels:
            print(f"    - {hw}")
    else:
        print("    无")

    print("\n[4] 硬件编码器检测结果...")
    hw_info = detect_hardware_info()
    if hw_info.isAvailable and hw_info.vendor:
        print(f"    检测到可用硬件: {hw_info.vendor.upper()}")
        print(f"    GPU 型号: {hw_info.gpu_name}")
        print(f"    H.264 编码器: {hw_info.h264_encoder}")
        print(f"    HEVC 编码器: {hw_info.hevc_encoder}")
        print(f"    AV1 编码器: {hw_info.av1_encoder}")
    else:
        print("    无可用硬件编码器，将使用 CPU 软编码")

    print("\n[5] 推荐配置...")
    if hw_info.isAvailable and hw_info.vendor:
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
    print("\n[6] 前端 API 返回参数...")
    print(json.dumps(hw_info.to_api_response(), indent=2, ensure_ascii=False))
    print("\n" + "=" * 60)


if __name__ == "__main__":
    enable_detection = (
        os.environ.get("ENABLE_HARDWARE_ACCELERATION_DETECTION", "true").lower()
        == "true"
    )

    if not enable_detection:
        print("硬件加速检测已通过环境变量禁用")
    else:
        print_full_report()
