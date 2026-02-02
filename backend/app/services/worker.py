# backend/app/services/worker.py

import asyncio
import collections


user_task_queues = collections.defaultdict(asyncio.Queue)


async def worker():
    """
    一个永续运行的后台工作者，从各个用户队列中轮流获取任务并执行。
    """
    while True:
        user_ids = list(user_task_queues.keys())
        if not user_ids:
            await asyncio.sleep(0.1)
            continue

        for user_id in user_ids[:]:
            try:
                if not user_task_queues[user_id].empty():
                    task_details = user_task_queues[user_id].get_nowait()

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

                    user_task_queues[user_id].task_done()
                    break
            except asyncio.QueueEmpty:
                continue
            except Exception:
                continue

        if all(user_task_queues[user_id].empty() for user_id in user_ids):
            await asyncio.sleep(0.01)
