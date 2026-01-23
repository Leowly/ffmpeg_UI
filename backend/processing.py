# backend/processing.py

import asyncio
import logging
import os
import shlex
import subprocess
import sys
import time
from queue import Empty, Queue
from threading import Thread
from typing import Tuple, Dict

from fastapi import WebSocket

from . import crud, schemas
from .database import SessionLocal

import collections

# 为每个用户维护一个独立的任务队列
user_task_queues = collections.defaultdict(asyncio.Queue)

# 全局字典存储正在运行的进程句柄
active_ffmpeg_processes: Dict[int, subprocess.Popen] = {}

async def worker():
    """
    一个永续运行的后台工作者，从各个用户队列中轮流获取任务并执行。
    """
    while True:
        # 循环检查所有用户队列，实现公平调度
        user_ids = list(user_task_queues.keys())
        if not user_ids:
            # 如果没有用户队列，短暂等待后继续
            await asyncio.sleep(0.1)
            continue

        for user_id in user_ids[:]:
            try:
                # 尝试从当前用户队列获取任务（非阻塞）
                if not user_task_queues[user_id].empty():
                    task_details = user_task_queues[user_id].get_nowait()

                    print(f"Worker picked up task: {task_details['task_id']} for user {task_details['owner_id']}")
                    try:
                        # 调用我们现有的处理函数来执行任务
                        await run_ffmpeg_process(
                            task_id=task_details['task_id'],
                            command_args=task_details['command_args'],
                            total_duration=task_details['total_duration'],
                            conn_manager=task_details['conn_manager'],
                            display_command=task_details['display_command'],
                            temp_output_path=task_details['temp_output_path'],
                            final_output_path=task_details['final_output_path'],
                            final_display_name=task_details['final_display_name'],
                        )
                    except Exception as e:
                        print(f"An error occurred while processing task {task_details['task_id']}: {e}")

                    # 标记任务完成，以便队列可以继续处理
                    user_task_queues[user_id].task_done()
                    break  # 处理完一个任务后继续下一轮循环
            except asyncio.QueueEmpty:
                # 当前用户队列为空，继续检查下一个用户
                continue
            except Exception:
                # 如果处理过程中出现其他异常，继续检查下一个用户
                continue

        # 避免忙等待
        if all(user_task_queues[user_id].empty() for user_id in user_ids):
            await asyncio.sleep(0.01)  # 短暂休眠

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, task_id: int):
        await websocket.accept()
        self.active_connections[task_id] = websocket

    def disconnect(self, task_id: int):
        if task_id in self.active_connections:
            del self.active_connections[task_id]

    async def send_progress(self, task_id: int, progress: int, status: str | None = None):
        if task_id in self.active_connections:
            message = {"progress": progress}
            if status:
                message["status"] = status
            await self.active_connections[task_id].send_json(message)

# 创建一个全局的 manager 实例
manager = ConnectionManager()

# --- FFmpeg Execution Logic ---
def run_ffmpeg_blocking(
    command_args: list,
    task_id: int,
    total_duration: float,
    main_loop: asyncio.AbstractEventLoop,
    conn_manager: ConnectionManager,
) -> Tuple[bool, str]:
    import re

    time_re = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
    logger = logging.getLogger("ffmpeg_runner")
    proc = None

    try:
        proc = subprocess.Popen(
            command_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        active_ffmpeg_processes[task_id] = proc

        q: Queue[str | None] = Queue()

        def reader_thread(pipe, queue):
            try:
                if pipe:
                    for line in iter(pipe.readline, ''):
                        queue.put(line)
            finally:
                if pipe:
                    pipe.close()
                queue.put(None)

        if proc.stderr:
            Thread(target=reader_thread, args=(proc.stderr, q), daemon=True).start()

        stderr_lines: list[str] = []
        last_progress = -1
        last_update_time = time.time()

        while True:
            try:
                # 依然设置 timeout 防止极端的死锁情况，但正常情况下不会触发
                line = q.get(timeout=30)
                
                if line is None:
                    break
                
                stderr_lines.append(line)
                m = time_re.search(line)
                if m:
                    try:
                        h, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
                        elapsed = h * 3600 + mm * 60 + ss
                        if total_duration > 0:
                            progress = int(min(99, (elapsed / total_duration) * 100))
                            
                            if progress >= last_progress + 10 or time.time() - last_update_time >= 3:
                                if progress < 100:
                                    future = asyncio.run_coroutine_threadsafe(
                                        conn_manager.send_progress(task_id, progress), main_loop
                                    )
                                    future.result()

                                    db = SessionLocal()
                                    try:
                                        crud.update_task(db, task_id=task_id, progress=progress)
                                    finally:
                                        db.close()
                                last_progress = progress
                                last_update_time = time.time()

                    except Exception:
                        pass
            except Empty:
                # 只有当 30秒内 既没有日志也没有 None 时才会进这里
                if proc.poll() is not None:
                    break
                else:
                    raise subprocess.TimeoutExpired(proc.args, 30)

        proc.wait()
        full_stderr = "".join(stderr_lines)

        if proc.returncode == 0:
            return True, full_stderr
        else:
            # stdout 已经是 DEVNULL 了，所以只看 stderr
            return False, full_stderr

    except FileNotFoundError:
        logger.error(f"FFmpeg command not found for task {task_id}.")
        return False, "FFmpeg executable not found."
    
    except subprocess.TimeoutExpired:
        error_msg = "FFmpeg process timed out."
        logger.error(f"FFmpeg process for task {task_id} timed out.")
        if proc:
            proc.kill()
        return False, error_msg

    except Exception as e:
        logger.error(f"Exception in blocking runner for task {task_id}: {e!r}", exc_info=True)
        return False, str(e)

    finally:
        if task_id in active_ffmpeg_processes:
            del active_ffmpeg_processes[task_id]

def terminate_task_process(task_id: int):
    if task_id in active_ffmpeg_processes:
        proc = active_ffmpeg_processes[task_id]
        print(f"Terminating FFmpeg process for task {task_id}")
        proc.kill() # 或者 proc.terminate()
        return True
    return False


async def run_ffmpeg_process(
    task_id: int,
    command_args: list,
    total_duration: float,
    conn_manager: ConnectionManager,
    display_command: str = "",
    temp_output_path: str = "",
    final_output_path: str = "",
    final_display_name: str = ""
):
    db = SessionLocal()
    logger = logging.getLogger("ffmpeg_runner")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)

    try:
        logger.info(f"run_ffmpeg_process: start task_id={task_id}, command={display_command}")
        crud.update_task(db, task_id=task_id, status="processing", progress=0)

        loop = asyncio.get_running_loop()

        success, full_stderr = await loop.run_in_executor(
            None,
            run_ffmpeg_blocking,
            command_args,
            task_id,
            total_duration,
            loop,
            conn_manager
        )

        if success:
            logger.info(f"Task {task_id} completed successfully.")
            try:
                if os.path.exists(final_output_path):
                    os.remove(final_output_path)
                os.replace(temp_output_path, final_output_path)

                task = crud.get_task(db, task_id)
                new_db_file = None
                if task:
                    new_file_schema = schemas.FileCreate(
                        filename=final_display_name or os.path.basename(final_output_path),
                        filepath=final_output_path,
                        status="processed"
                    )
                    new_db_file = crud.create_user_file(db=db, file=new_file_schema, user_id=task.owner_id)

                crud.update_task(
                    db,
                    task_id=task_id,
                    status="completed",
                    details=full_stderr,
                    progress=100,
                    result_file_id=new_db_file.id if new_db_file else None
                )
                await conn_manager.send_progress(task_id, 100, "completed")
                logger.info(f"Task {task_id} post-processing finished.")

            except Exception as e:
                error_msg = f"Post-processing failed: {e!r}"
                logger.error(error_msg, exc_info=True)
                crud.update_task(db, task_id=task_id, status="failed", details=error_msg)
                await conn_manager.send_progress(task_id, 100, "failed")
        else:
            logger.error(f"Task {task_id} failed. Stderr: {full_stderr}")
            crud.update_task(db, task_id=task_id, status="failed", details=full_stderr)
            await conn_manager.send_progress(task_id, 100, "failed")

    except Exception as e:
        logger.error(f"Exception in async wrapper for task {task_id}: {e!r}", exc_info=True)
        crud.update_task(db, task_id=task_id, status="failed", details=str(e))
    finally:
        # Cleanup temporary files to ensure they're removed even if the process fails
        if os.path.exists(temp_output_path) and temp_output_path != final_output_path:
            try:
                os.remove(temp_output_path)
                logger.info(f"Cleaned up temporary file: {temp_output_path}")
            except OSError as e:
                logger.error(f"Failed to remove temporary file {temp_output_path}: {e}")

        conn_manager.disconnect(task_id)
        db.close()