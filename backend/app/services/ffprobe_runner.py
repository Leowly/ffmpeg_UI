from typing import Tuple


def run_ffprobe_sync(path: str) -> Tuple[int, str, str]:
    import subprocess

    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            creationflags=0,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        raise
