# Re-export everything from the new modules for backward compatibility

from .manager import ConnectionManager, manager
from .worker import worker, global_queue
from .ffmpeg_runner import (
    run_ffmpeg_process,
    run_ffmpeg_blocking,
    terminate_task_process,
    active_ffmpeg_processes,
)

__all__ = [
    "ConnectionManager",
    "manager",
    "worker",
    "global_queue",
    "run_ffmpeg_process",
    "run_ffmpeg_blocking",
    "terminate_task_process",
    "active_ffmpeg_processes",
]
