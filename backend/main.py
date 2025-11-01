# main.py - FastAPI app entry point
import os
import uuid
import subprocess
import json
import asyncio
import logging
import shlex
import sys
import threading
import time
from typing import cast, List, Tuple, Dict

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    UploadFile,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse, JSONResponse
import aiofiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from . import crud, models, schemas, security
from .database import SessionLocal, engine

# --- WebSocket Connection Manager ---
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

manager = ConnectionManager()

def detect_video_codec(input_path: str) -> str:
    """返回输入视频的编码名称，例如 'av1', 'h264', 'hevc'"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=nw=1:nk=1",
            input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return ""

if sys.platform == "win32":
    print(">>> Gemini: Running on Windows. Attempting to set Proactor event loop policy...")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print(">>> Gemini: Policy set to Proactor.")
    except Exception as e:
        print(f">>> Gemini: Could not set Proactor policy: {e}")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

# --- CORS Configuration ---
origins = [
    "http://localhost", 
    "http://localhost:5173",
    "https://ffmpeg.0426233.xyz",
    "https://*.capacitor.localhost",
    "capacitor://localhost",
    "ionic://localhost",
    "https://localhost"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    allow_origin_regex=r"https://.*\.capacitor\.localhost"
)

# --- Configuration ---
UPLOAD_DIRECTORY = "./backend/workspaces"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

def reconstruct_file_path(stored_path: str, user_id: int) -> str | None:
    if os.path.exists(stored_path):
        return stored_path
    expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(user_id))
    unique_filename = os.path.basename(stored_path)
    reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)
    if os.path.exists(reconstructed_file_path):
        return reconstructed_file_path
    return None

# --- WebSocket-enabled FFmpeg Execution ---
def run_ffmpeg_blocking(
    command_args: list,
    task_id: int,
    total_duration: float,
    main_loop: asyncio.AbstractEventLoop,
    manager: ConnectionManager,
) -> Tuple[bool, str]:
    import re
    from queue import Queue, Empty
    from threading import Thread

    time_re = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
    logger = logging.getLogger("ffmpeg_runner")
    proc = None

    try:
        proc = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        q: Queue[str] = Queue()

        def reader_thread(pipe, queue):
            try:
                if pipe:
                    for line in iter(pipe.readline, ''):
                        queue.put(line)
            finally:
                if pipe:
                    pipe.close()

        if proc.stderr:
            Thread(target=reader_thread, args=(proc.stderr, q), daemon=True).start()

        stderr_lines: list[str] = []
        last_progress = -1
        last_update_time = time.time()

        while True:
            try:
                line = q.get(timeout=30)
                if not line:
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
                                    # Update WebSocket
                                    future = asyncio.run_coroutine_threadsafe(
                                        manager.send_progress(task_id, progress), main_loop
                                    )
                                    future.result()

                                    # Update database
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
                if proc.poll() is not None:
                    break
                else:
                    raise subprocess.TimeoutExpired(proc.args, 30)

        proc.wait()
        full_stderr = "".join(stderr_lines)

        if proc.returncode == 0:
            return True, full_stderr
        else:
            if not full_stderr and proc.stdout:
                full_stderr = proc.stdout.read()
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

# --- Refactored Async Task Wrapper ---
async def run_ffmpeg_process(
    task_id: int, 
    command_args: list, 
    total_duration: float,
    manager: ConnectionManager,
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
            manager
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
                # Send final progress update and status update
                await manager.send_progress(task_id, 100, "completed") # Final progress update
                logger.info(f"Task {task_id} post-processing finished.")

            except Exception as e:
                error_msg = f"Post-processing failed: {e!r}"
                logger.error(error_msg, exc_info=True)
                crud.update_task(db, task_id=task_id, status="failed", details=error_msg)
                await manager.send_progress(task_id, 100, "failed") # Indicate processing is done even if failed
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
        else:
            logger.error(f"Task {task_id} failed. Stderr: {full_stderr}")
            crud.update_task(db, task_id=task_id, status="failed", details=full_stderr)
            await manager.send_progress(task_id, 100, "failed") # Indicate processing is done
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)

    except Exception as e:
        logger.error(f"Exception in async wrapper for task {task_id}: {e!r}", exc_info=True)
        crud.update_task(db, task_id=task_id, status="failed", details=str(e))
    finally:
        manager.disconnect(task_id)
        db.close()

# --- Dependencies ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
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

# --- WebSocket Endpoint ---
@app.websocket("/ws/progress/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: int):
    await manager.connect(websocket, task_id)
    try:
        while True:
            await websocket.receive_text() # Keep connection open
    except WebSocketDisconnect:
        manager.disconnect(task_id)

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
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/me", response_model=schemas.User, tags=["Users"])
def read_users_me(current_user: models.User = Depends(get_current_user)):
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
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = db_file.filepath
    resolved = await asyncio.get_running_loop().run_in_executor(
        None, reconstruct_file_path, file_path, current_user.id
    )
    if not resolved:
        raise HTTPException(status_code=404, detail="File not found on server")
    file_path = resolved

    def run_ffprobe_sync(path: str) -> Tuple[int, str, str]:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path,
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                errors='ignore',
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            raise

    try:
        loop = asyncio.get_running_loop()
        returncode, stdout, stderr = await loop.run_in_executor(
            None, run_ffprobe_sync, file_path
        )

        if returncode != 0:
            raise HTTPException(status_code=500, detail=f"ffprobe error: {stderr}")

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Could not parse ffprobe output")

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffprobe command not found.")
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
        resolved_file_path = None

        exists = await loop.run_in_executor(None, os.path.exists, current_file_path)
        if exists:
            resolved_file_path = current_file_path
        else:
            resolved_candidate = await loop.run_in_executor(None, reconstruct_file_path, current_file_path, current_user.id)
            if resolved_candidate:
                resolved_file_path = resolved_candidate

        if resolved_file_path:
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
                    temp_path=resolved_file_path
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
        raise HTTPException(status_code=400, detail="Invalid file ID")

    db_file = crud.get_file_by_id(db, file_id=file_id_int)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

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

def construct_ffmpeg_command(input_path: str, output_path: str, params: schemas.ProcessPayload) -> list:
    video_codec = params.videoCodec
    audio_codec = params.audioCodec
    container = params.container
    is_audio_only_output = container in ['mp3', 'flac', 'wav', 'aac', 'ogg']

    if not is_audio_only_output and video_codec != 'copy':
        if container == 'mp4' and video_codec not in ['libx264', 'libx265']:
            video_codec = 'libx264'
        elif container == 'mkv' and video_codec not in ['libx264', 'libx265', 'libaom-av1', 'vp9']:
            video_codec = 'libx264'
        elif container == 'mov' and video_codec not in ['libx264', 'libx265']:
            video_codec = 'libx264'

    if audio_codec != 'copy':
        if container in ['mp4', 'mov'] and audio_codec not in ['aac', 'mp3']:
            audio_codec = 'aac'
        elif container == 'mkv' and audio_codec not in ['aac', 'mp3', 'opus', 'flac']:
            audio_codec = 'aac'
        elif container == 'mp3':
            audio_codec = 'libmp3lame'
        elif container == 'flac':
            audio_codec = 'flac'
        elif container == 'aac':
            audio_codec = 'aac'
        elif container == 'wav':
            audio_codec = 'pcm_s16le'

    command = ["ffmpeg", "-y"]
    input_codec = detect_video_codec(input_path)
    if input_codec == 'av1':
        command.extend(["-c:v", "av1_cuvid"])
    command.extend(["-analyzeduration", "20M", "-probesize", "20M"])
    command.extend(["-i", input_path])

    if params.startTime > 0:
        command.extend(["-ss", str(params.startTime)])
    if params.endTime < params.totalDuration:
        command.extend(["-to", str(params.endTime)])

    if is_audio_only_output:
        command.append("-vn")
        command.extend(["-map", "0:a?"])
    else:
        command.extend(["-map", "0:v?", "-map", "0:a?"])

    command.extend(["-fflags", "+genpts", "-avoid_negative_ts", "make_zero"])

    if not is_audio_only_output:
        if video_codec != "copy":
            command.extend(["-c:v", video_codec])
            if params.startTime > 0 or params.endTime < params.totalDuration:
                command.extend(["-force_key_frames", "expr:eq(n,0)"])
            if params.videoBitrate:
                command.extend(["-b:v", f"{params.videoBitrate}k"])
            if params.resolution:
                command.extend(["-s", f"{params.resolution.width}x{params.resolution.height}"])
        else:
            command.extend(["-c:v", "copy"])

    if audio_codec != "copy":
        command.extend(["-c:a", audio_codec])
        if params.audioBitrate:
            command.extend(["-b:a", f"{params.audioBitrate}k"])
    else:
        command.extend(["-c:a", "copy"])

    command.append(output_path)
    return command

@app.post("/api/process", response_model=List[schemas.Task], tags=["Files"])
async def process_files(
    payload: schemas.ProcessPayload,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    created_tasks = []
    logging.getLogger("ffmpeg_runner").info(f"process_files payload: {payload}")
    
    for file_id_str in payload.files:
        try:
            file_id = int(file_id_str)
        except ValueError:
            continue

        db_file = crud.get_file_by_id(db, file_id=file_id)
        if not db_file or db_file.owner_id != current_user.id:
            continue

        input_path = os.path.normpath(db_file.filepath)
        original_filename_base, _ = os.path.splitext(db_file.filename)
        final_display_name = f"{original_filename_base}_processed.{payload.container}"
        final_disk_filename = f"{uuid.uuid4()}.{payload.container}"
        final_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), final_disk_filename))
        temp_output_filename = f"{uuid.uuid4()}.{payload.container}"
        temp_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), temp_output_filename))
        command = construct_ffmpeg_command(input_path, temp_output_path, payload)

        if sys.platform == "win32":
            ffmpeg_command_str = subprocess.list2cmdline(command)
        else:
            ffmpeg_command_str = " ".join(shlex.quote(p) for p in command)

        task_in = schemas.TaskCreate(
            ffmpeg_command=ffmpeg_command_str,
            source_filename=db_file.filename
        )
        db_task = crud.create_task(db=db, task=task_in, owner_id=current_user.id, output_path=final_output_path)

        background_tasks.add_task(
            run_ffmpeg_process, 
            db_task.id, 
            command, 
            payload.totalDuration,
            manager,
            display_command=ffmpeg_command_str, 
            temp_output_path=temp_output_path,
            final_output_path=final_output_path,
            final_display_name=final_display_name,
        )
        created_tasks.append(db_task)

    if not created_tasks:
        raise HTTPException(status_code=404, detail="No valid files found.")
    
    return created_tasks

@app.get("/api/tasks", response_model=List[schemas.Task], tags=["Tasks"])
def get_tasks(
    skip: int = 0,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.get_user_tasks(db, owner_id=current_user.id, skip=skip)

@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"])
def delete_task(
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_task = crud.get_task(db, task_id=task_id)
    if db_task and db_task.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    if db_task:
        crud.delete_task(db, task_id=task_id)
    
    return

@app.get("/api/task-status/{taskId}", tags=["Files"])
def get_task_status(
    taskId: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_id = int(taskId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")
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
        raise HTTPException(status_code=400, detail="Invalid file ID")

    db_file = crud.get_file_by_id(db, file_id=file_id)
    if not db_file or db_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = db_file.filepath
    loop = asyncio.get_running_loop()
    resolved = await loop.run_in_executor(None, reconstruct_file_path, file_path, current_user.id)
    if resolved:
        file_path = resolved

    exists = await loop.run_in_executor(None, os.path.exists, file_path)
    if exists:
        await loop.run_in_executor(None, os.remove, file_path)

    await loop.run_in_executor(None, crud.delete_file, db, file_id)

    return {"message": f"File {filename} deleted."}

@app.post("/api/upload", response_model=schemas.FileResponseForFrontend, tags=["Files"])
async def upload_file(
    file: UploadFile,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        user_upload_directory = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        os.makedirs(user_upload_directory, exist_ok=True)
        file_location = os.path.normpath(os.path.join(user_upload_directory, unique_filename))

        async with aiofiles.open(file_location, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                await out_f.write(chunk)

        loop = asyncio.get_running_loop()
        file_size = await loop.run_in_executor(None, os.path.getsize, file_location)

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

        return schemas.FileResponseForFrontend(
            uid=str(db_file.id),
            id=str(db_file.id),
            name=db_file.filename,
            status="done",
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
    return {"message": "Welcome to the FFmpeg UI Backend"}