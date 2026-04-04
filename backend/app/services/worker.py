# backend/app/services/worker.py

import asyncio
import logging

"""Global worker queue and worker coroutine.

This module previously maintained per-user queues to dispatch tasks.
To avoid CPU spinning and memory leaks from offline users, we now use a
single global queue that all producers enqueue into and the single worker
consumes from. The consumer blocks on get(), eliminating busy-wait and
extensive polling.
"""

global_queue: asyncio.Queue = asyncio.Queue()
logger = logging.getLogger(__name__)


async def worker():
    """A perpetual background worker that blocks on the global queue and executes tasks."""
    while True:
        task_details = await global_queue.get()

        logger.info(
            "Worker picked up task: %s for user %s",
            task_details["task_id"],
            task_details["owner_id"],
        )
        try:
            from app.services.ffmpeg_runner import run_ffmpeg_process

            await run_ffmpeg_process(
                task_id=task_details["task_id"],
                command_args=task_details["command_args"],
                total_duration=task_details["total_duration"],
                conn_manager=task_details["conn_manager"],
                display_command=task_details["display_command"],
                temp_output_path=task_details["temp_output_path"],
                final_output_path=task_details["final_output_path"],
                final_display_name=task_details["final_display_name"],
            )
        except Exception:
            logger.exception(
                "An error occurred while processing task %s", task_details["task_id"]
            )
        finally:
            logger.debug("Task %s completed", task_details["task_id"])
            global_queue.task_done()
