# backend/app/services/worker.py

import asyncio
import logging

"""Per-user worker queue with Round-Robin fair scheduling.

This module maintains per-user queues to enable fair scheduling across users.
Key features:
- Zero CPU spinning: worker blocks on active_users.get()
- No memory leak: user queues are cleaned up when empty
- Fair scheduling: users take turns (A -> B -> A -> B)
"""

logger = logging.getLogger(__name__)

# Per-user task queues
user_queues: dict[int, asyncio.Queue] = {}
# Queue of active users (those with pending tasks)
active_users: asyncio.Queue = asyncio.Queue()
# Lock to protect user_queues dictionary modifications
queue_lock = asyncio.Lock()


async def enqueue_task(user_id: int, task_details: dict):
    """Enqueue a task into the corresponding user's queue."""
    async with queue_lock:
        if user_id not in user_queues:
            # Create new queue for this user and add to active users pool
            user_queues[user_id] = asyncio.Queue()
            await active_users.put(user_id)

        # Put task into user's private queue
        await user_queues[user_id].put(task_details)
        logger.info("Task %s enqueued for user %s", task_details["task_id"], user_id)


async def worker(worker_id: int = 1):
    """Background worker coroutine with Round-Robin fair scheduling."""
    while True:
        # 1. Block until there is an active user with pending tasks (zero CPU spin)
        user_id = await active_users.get()

        # 2. Safely extract task
        async with queue_lock:
            queue = user_queues.get(user_id)
            if not queue or queue.empty():
                # Safety fallback - shouldn't happen in theory
                active_users.task_done()
                continue

            # Get one task from user's queue
            task_details = queue.get_nowait()

        # 3. Process task (no lock held, doesn't block other users)
        logger.info(
            "Worker-%d processing task %s for user %s",
            worker_id,
            task_details["task_id"],
            user_id,
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
                "Worker-%d: Error processing task %s",
                worker_id,
                task_details["task_id"],
            )
        finally:
            logger.debug(
                "Worker-%d: Task %s completed", worker_id, task_details["task_id"]
            )

            # 4. Re-evaluate user status after task completion
            async with queue_lock:
                queue = user_queues.get(user_id)
                if queue and not queue.empty():
                    # User has more tasks - re-queue for fair round-robin
                    await active_users.put(user_id)
                else:
                    # Queue is empty - clean up to prevent memory leak
                    if user_id in user_queues:
                        del user_queues[user_id]
                        logger.info(
                            "Queue empty for user %s, resources cleaned up.", user_id
                        )

            active_users.task_done()
