# main.py - FastAPI app entry point
import os
import uuid
import subprocess
import json
import asyncio
import logging
import shlex
import sys
from typing import cast, List, Tuple

# 策略设置现在由 run.py 处理，但保留在这里也无害
if sys.platform == "win32":
    print(">>> Gemini: Running on Windows. Attempting to set Proactor event loop policy...")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print(">>> Gemini: Policy set to Proactor.")
    except Exception as e:
        print(f">>> Gemini: Could not set Proactor policy: {e}")

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
import aiofiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from . import crud, models, schemas, security
from .database import SessionLocal, engine, DB_PATH

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

# --- CORS Configuration ---
origins = ["http://localhost", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
UPLOAD_DIRECTORY = "./backend/workspaces"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)


def reconstruct_file_path(stored_path: str, user_id: int) -> str | None:
    """Try to reconstruct a file path for backward compatibility.

    If the stored_path exists, return it. Otherwise try to find the file under
    UPLOAD_DIRECTORY/<user_id>/<basename(stored_path)> and return that if it exists.
    Return None if no valid path found.
    """
    if os.path.exists(stored_path):
        return stored_path

    expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(user_id))
    unique_filename = os.path.basename(stored_path)
    reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)

    if os.path.exists(reconstructed_file_path):
        return reconstructed_file_path

    return None

# --- 核心修改：新的阻塞式 FFmpeg 执行函数 ---
def run_ffmpeg_blocking(
    command_args: list, task_id: int, total_duration: float
) -> Tuple[bool, str]:
    """
    在一个独立的线程中执行的、阻塞的 FFmpeg 函数。
    这避免了与 asyncio 事件循环的直接冲突。
    返回一个元组 (success: bool, full_stderr: str)
    """
    from .database import SessionLocal as TaskSessionLocal
    from . import crud
    import re

    db = TaskSessionLocal()
    time_re = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
    logger = logging.getLogger("ffmpeg_runner")

    try:
        # 使用经典的 subprocess.Popen，它在任何环境下都能工作
        proc = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # 使用 text=True 自动解码
            errors='ignore',
            # 在Windows上隐藏命令行窗口
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        stderr_lines: list[str] = []
        last_progress = -1

        # 逐行读取 stderr。因为在后台线程，这里的阻塞是安全的。
        if proc.stderr:
            for line in iter(proc.stderr.readline, ""):
                if not line:
                    break
                logger.info(line.strip())
                stderr_lines.append(line)
                m = time_re.search(line)
                if m:
                    try:
                        h, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
                        elapsed = h * 3600 + mm * 60 + ss
                        if total_duration > 0:
                            progress = int(min(100, (elapsed / total_duration) * 100))
                            if progress != last_progress:
                                # 注意：频繁的数据库写入可能会成为瓶颈，但对于单个任务是可接受的
                                crud.update_task(db, task_id=task_id, status="processing", progress=progress, details=''.join(stderr_lines[-20:]))
                                last_progress = progress
                    except Exception:
                        pass
        
        # 等待进程结束
        proc.wait()
        full_stderr = "".join(stderr_lines)

        if proc.returncode == 0:
            return True, full_stderr
        else:
            # 如果 proc.stderr 为空，尝试读取 stdout 获取错误信息
            if not full_stderr and proc.stdout:
                full_stderr = proc.stdout.read()
            return False, full_stderr

    except Exception as e:
        logger.error(f"Exception in blocking runner for task {task_id}: {e!r}", exc_info=True)
        return False, str(e)
    finally:
        db.close()


# --- 核心修改：重构后的异步任务包装器 ---
async def run_ffmpeg_process(
    task_id: int, 
    command_args: list, 
    total_duration: float, 
    display_command: str = "", 
    temp_output_path: str = "", 
    final_output_path: str = ""
):
    """
    异步包装器，使用 run_in_executor 将阻塞的 FFmpeg 任务移到后台线程。
    """
    from .database import SessionLocal as TaskSessionLocal
    from . import crud, schemas

    db = TaskSessionLocal()
    logger = logging.getLogger("ffmpeg_runner")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)

    try:
        logger.info(f"run_ffmpeg_process: start task_id={task_id}, command={display_command}")
        crud.update_task(db, task_id=task_id, status="processing")

        loop = asyncio.get_running_loop()
        
        # 将阻塞函数和其参数传递给执行器
        success, full_stderr = await loop.run_in_executor(
            None,  # 使用默认的 ThreadPoolExecutor
            run_ffmpeg_blocking,
            command_args,
            task_id,
            total_duration
        )

        if success:
            logger.info(f"Task {task_id} blocking process completed successfully.")
            try:
                if os.path.exists(final_output_path):
                    os.remove(final_output_path)
                os.rename(temp_output_path, final_output_path)
                
                task = crud.get_task(db, task_id)
                if task:
                    new_file_schema = schemas.FileCreate(
                        filename=os.path.basename(final_output_path),
                        filepath=final_output_path,
                        status="processed"
                    )
                    crud.create_user_file(db=db, file=new_file_schema, user_id=task.owner_id)
                
                crud.update_task(db, task_id=task_id, status="completed", details=full_stderr, progress=100)
                logger.info(f"Task {task_id} post-processing finished. Output: {final_output_path}")

            except Exception as e:
                error_msg = f"FFmpeg succeeded, but post-processing failed: {e!r}"
                logger.error(error_msg, exc_info=True)
                crud.update_task(db, task_id=task_id, status="failed", details=error_msg)
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
        else:
            logger.error(f"Task {task_id} blocking process failed. Stderr: {full_stderr}")
            crud.update_task(db, task_id=task_id, status="failed", details=full_stderr, progress=0)
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)

    except Exception as e:
        logger.error(f"Exception in async wrapper for task {task_id}: {e!r}", exc_info=True)
        crud.update_task(db, task_id=task_id, status="failed", details=str(e))
    finally:
        db.close()


# --- Dependencies ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    """Dependency to get a DB session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = security.verify_token(token, credentials_exception)
    username: str | None = token_data.get("sub")
    if username is None:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

# --- API Endpoints ---

@app.post("/token", response_model=schemas.Token, tags=["Users"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not security.verify_password(form_data.password, cast(str, user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/users/", response_model=schemas.User, tags=["Users"])
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user.
    - **username**: The desired username (must be unique).
    - **password**: The user's password.
    """
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)


@app.get("/users/me", response_model=schemas.User, tags=["Users"])
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """Get the current logged-in user's information."""
    return current_user


@app.get("/api/file-info", tags=["Files"])
async def get_file_info(
    filename: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_id = int(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found or not owned by user")
    file_path = db_file.filepath

    # Use helper to resolve potential moved/legacy file locations
    resolved = reconstruct_file_path(file_path, current_user.id)
    if not resolved:
        raise HTTPException(status_code=404, detail="File not found on server")
    file_path = resolved

    try:
        # Use asyncio subprocess to avoid blocking the event loop
        command = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            # decode stderr for readable error message
            err_text = stderr.decode(errors="ignore") if stderr else ""
            raise HTTPException(status_code=500, detail=f"ffprobe error: {err_text}")

        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Could not parse ffprobe output")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/files", response_model=List[schemas.FileResponseForFrontend], tags=["Files"])
async def read_user_files(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_files = crud.get_user_files(db, user_id=current_user.id)
    response_files = []
    loop = asyncio.get_running_loop()

    for db_file in db_files:
        current_file_path = db_file.filepath
        resolved_file_path = None  # Initialize to None

        # Check existence using executor to avoid blocking
        exists = await loop.run_in_executor(None, os.path.exists, current_file_path)
        if exists:
            resolved_file_path = current_file_path
        else:
            # run reconstruct_file_path in executor as it uses os.path.exists internally
            resolved_candidate = await loop.run_in_executor(None, reconstruct_file_path, current_file_path, current_user.id)
            if resolved_candidate:
                resolved_file_path = resolved_candidate
                # Optionally update DB: crud.update_file_path(db, db_file.id, resolved_candidate)

        if resolved_file_path:  # Only proceed if a valid path was found
            file_size = await loop.run_in_executor(None, os.path.getsize, resolved_file_path)
            response_files.append(schemas.FileResponseForFrontend(
                uid=str(db_file.id),
                id=str(db_file.id),
                name=db_file.filename,
                status=db_file.status,
                size=file_size,
                response=schemas.FileResponseInner(
                    file_id=str(db_file.id),
                    original_name=db_file.filename,
                    temp_path=resolved_file_path  # Use the resolved path here
                )
            ))

    return response_files


@app.get("/api/download-file/{file_id}", tags=["Files"])
async def download_file(
    file_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_id_int = int(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    db_file = crud.get_file_by_id(db, file_id=file_id_int)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found or not owned by user")

    file_path = db_file.filepath
    loop = asyncio.get_running_loop()
    resolved = await loop.run_in_executor(None, reconstruct_file_path, file_path, current_user.id)
    if resolved:
        file_path = resolved
    else:
        raise HTTPException(status_code=404, detail="File not found on server")

    async def file_iterator(path: str, chunk_size: int = 1024 * 1024):
        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    headers = {"Content-Disposition": f'attachment; filename="{db_file.filename}"'}
    return StreamingResponse(file_iterator(file_path), media_type="application/octet-stream", headers=headers)

@app.post("/api/process", response_model=List[schemas.Task], tags=["Files"])
async def process_files(
    payload: schemas.ProcessPayload,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    接收一个或多个文件及处理参数，为每个文件创建一个后台 FFmpeg 处理任务。
    处理后的文件将以 "_processed" 后缀保存在同一目录下，并作为新文件添加到用户的文件列表。
    """
    created_tasks = []
    # debug: print incoming payload
    print(f"process_files called by user={current_user.username} payload_files={payload.files} container={payload.container}")
    logging.getLogger("ffmpeg_runner").info(f"process_files payload: {payload}")
    
    for file_id_str in payload.files:
        try:
            file_id = int(file_id_str)
        except ValueError:
            # 在循环中跳过无效ID
            continue

        db_file = crud.get_file_by_id(db, file_id=file_id)
        if not db_file or db_file.owner_id != current_user.id:
            print(f"process_files: file id {file_id} not owned by user {current_user.id}, skipping")
            logging.getLogger("ffmpeg_runner").warning(f"file id {file_id} not owned by user {current_user.id}, skipping")
            continue

        # --- 动态构建 FFmpeg 命令 (新逻辑) ---
        input_path = os.path.normpath(db_file.filepath)
        
        # 1. 获取不带扩展名的原始文件名和扩展名
        original_filename_base, _ = os.path.splitext(db_file.filename)

        # 2. 构造带有 "_processed" 后缀的最终目标文件名
        final_output_filename = f"{original_filename_base}_processed.{payload.container}"
        
        # 3. 确定最终处理完成后的文件在磁盘上的完整路径
        final_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), final_output_filename))
        
        # 4. 创建一个临时的、唯一的输出路径，FFmpeg 将先写入这里
        temp_output_filename = f"{uuid.uuid4()}.{payload.container}"
        temp_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), temp_output_filename))

        # 5. 构建 FFmpeg 命令列表
        #    使用 -y 参数可以在开发或重试时自动覆盖同名的临时文件
        command = ["ffmpeg", "-y"]

        # 时间裁剪 (Input seeking for speed and accuracy)
        if payload.startTime > 0:
            command.extend(["-ss", str(payload.startTime)])

        # 探测选项
        command.extend(["-probesize", "5M", "-analyzeduration", "10M"])

        # 输入文件
        command.extend(["-i", input_path])

        # 设置时长
        if payload.endTime < payload.totalDuration:
            duration = payload.endTime - payload.startTime
            if duration > 0:
                command.extend(["-t", str(duration)])

        # 可选的流映射
        command.extend(["-map", "0:v?", "-map", "0:a?"])

        # 视频编码
        command.extend(["-c:v", payload.videoCodec])
        if payload.videoCodec != 'copy':
            command.extend(["-pix_fmt", "yuv420p"])
            if payload.videoBitrate:
                command.extend(["-b:v", f"{payload.videoBitrate}k"])
            if payload.resolution:
                command.extend(["-s", f"{payload.resolution.width}x{payload.resolution.height}"])
        
        # 音频编码
        command.extend(["-c:a", payload.audioCodec])
        if payload.audioCodec != 'copy' and payload.audioBitrate:
            command.extend(["-b:a", f"{payload.audioBitrate}k"])

        # 6. 输出路径（关键：指向临时文件）
        command.append(temp_output_path)

        # 构造一个用于显示/存入 DB 的可读命令字符串
        if sys.platform == "win32":
            ffmpeg_command_str = subprocess.list2cmdline(command)
        else:
            ffmpeg_command_str = " ".join(shlex.quote(p) for p in command)

        logging.getLogger("ffmpeg_runner").info(f"Creating task for file_id={file_id} input={input_path} temp_output={temp_output_path} final_output={final_output_path}")
        logging.getLogger("ffmpeg_runner").info(f"FFmpeg command string: {ffmpeg_command_str}")

        # --- 创建数据库任务记录 ---
        task_in = schemas.TaskCreate(ffmpeg_command=ffmpeg_command_str)
        # 关键：我们将 `final_output_path` 存入数据库，这是任务最终产物的路径
        db_task = crud.create_task(db=db, task=task_in, owner_id=current_user.id, output_path=final_output_path)

        # --- 添加到后台任务队列 ---
        logging.getLogger("ffmpeg_runner").info(f"Queuing background task id={db_task.id}")
        # 传入所有需要的路径参数到后台任务
        background_tasks.add_task(
            run_ffmpeg_process, 
            db_task.id, 
            command, 
            payload.totalDuration, 
            display_command=ffmpeg_command_str, 
            temp_output_path=temp_output_path,
            final_output_path=final_output_path
        )
        created_tasks.append(db_task)

    if not created_tasks:
        raise HTTPException(
            status_code=404,
            detail="No valid files found to process for the given IDs."
        )
    
    return created_tasks


@app.get("/api/tasks", response_model=List[schemas.Task], tags=["Tasks"])
def get_tasks(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有处理任务"""
    return crud.get_user_tasks(db, owner_id=current_user.id)





@app.get("/api/task-status/{taskId}", tags=["Files"])
def get_task_status(
    taskId: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_id = int(taskId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found or not owned by user")
    return {"status": db_file.status}


@app.delete("/api/delete-file", tags=["Files"])
async def delete_user_file(
    filename: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_id = int(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found or not owned by user")

    # Delete physical file
    file_path = db_file.filepath
    loop = asyncio.get_running_loop()
    resolved = await loop.run_in_executor(None, reconstruct_file_path, file_path, current_user.id)
    if resolved:
        file_path = resolved

    exists = await loop.run_in_executor(None, os.path.exists, file_path)
    if exists:
        await loop.run_in_executor(None, os.remove, file_path)

    # Delete database record
    await loop.run_in_executor(None, crud.delete_file, db, file_id)

    return {"message": f"File {filename} deleted successfully"}


@app.post("/api/upload", response_model=schemas.FileResponseForFrontend, tags=["Files"])
async def upload_file(
    file: UploadFile,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Generate a unique filename to prevent collisions
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"

        # Create a user-specific directory
        user_upload_directory = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        os.makedirs(user_upload_directory, exist_ok=True)

        file_location = os.path.normpath(os.path.join(user_upload_directory, unique_filename))

        # Write file in chunks asynchronously
        async with aiofiles.open(file_location, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                await out_f.write(chunk)

        # Get file size after writing (use executor to call os.path.getsize)
        loop = asyncio.get_running_loop()
        file_size = await loop.run_in_executor(None, os.path.getsize, file_location)

        # Create a database entry for the uploaded file in executor to avoid blocking
        def db_create():
            return crud.create_user_file(
                db=db,
                file=schemas.FileCreate(
                    filename=file.filename,
                    filepath=file_location,
                    status="uploaded"
                ),
                user_id=current_user.id
            )

        db_file = await loop.run_in_executor(None, db_create)

        # Construct response to match frontend's UserFile interface
        return schemas.FileResponseForFrontend(
            uid=str(db_file.id),
            id=str(db_file.id),
            name=db_file.filename,
            status="done",  # Assuming 'done' after successful upload and DB entry
            size=file_size,
            response=schemas.FileResponseInner(
                file_id=str(db_file.id),
                original_name=db_file.filename,
                temp_path=db_file.filepath,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not upload file: {e}")


@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint providing a welcome message."""
    return {"message": "Welcome to the FFmpeg UI Backend"}