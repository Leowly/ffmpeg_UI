# backend/app/services/worker.py

import asyncio

"""Global worker queue and worker coroutine.

This module previously maintained per-user queues to dispatch tasks.
To avoid CPU spinning and memory leaks from offline users, we now use a
single global queue that all producers enqueue into and the single worker
consumes from. The consumer blocks on get(), eliminating busy-wait and
extensive polling.
"""

global_queue: asyncio.Queue = asyncio.Queue()


async def worker():
    """A perpetual background worker that blocks on the global queue and executes tasks."""
    while True:
        task_details = await global_queue.get()

        print(
            f"Worker picked up task: {task_details['task_id']} for user {task_details['owner_id']}"
        )
        try:
            from .ffmpeg_runner import run_ffmpeg_process

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
        except Exception as e:
            print(
                f"An error occurred while processing task {task_details['task_id']}: {e}"
            )
        finally:
            global_queue.task_done()
