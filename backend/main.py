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
from typing import cast, List, Tuple, Dict

# --- 全局进度缓存 ---
# 用于存储正在进行中的任务的实时进度
# 格式: {task_id: progress}
task_progress_cache: Dict[int, int] = {}
_progress_lock = threading.Lock()


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
# 策略设置现在由 run.py 处理，但保留在这里也无害
if sys.platform == "win32":
    print(">>> Gemini: Running on Windows. Attempting to set Proactor event loop policy...")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print(">>> Gemini: Policy set to Proactor.")
    except Exception as e:
        print(f">>> Gemini: Could not set Proactor policy: {e}")

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile,  BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
import aiofiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from . import crud, models, schemas, security
from .database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

# --- CORS Configuration ---
# 添加对Capacitor移动端的CORS支持
origins = [
    "http://localhost", 
    "http://localhost:5173",
    "https://ffmpeg.0426233.xyz",  # 您的部署地址
    "https://*.capacitor.localhost",  # Capacitor移动应用
    "capacitor://localhost",         # Capacitor本地URL
    "ionic://localhost",             # Ionic本地URL
    "https://localhost"              # 其他可能的本地地址
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # 暴露 Content-Disposition 头
    allow_origin_regex=r"https://.*\.capacitor\.localhost"  # 支持Capacitor的正则匹配
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
    使用非阻塞的输出读取和30秒的停滞超时。
    实时将进度更新到全局缓存中。
    返回一个元组 (success: bool, full_stderr: str)
    """
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
                            progress = int(min(100, (elapsed / total_duration) * 100))
                            if progress != last_progress:
                                # --- 核心修改: 更新全局缓存 ---
                                with _progress_lock:
                                    task_progress_cache[task_id] = progress
                                last_progress = progress
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
        logger.error(f"FFmpeg command not found for task {task_id}. Ensure ffmpeg is in the system's PATH.")
        return False, "FFmpeg executable not found. Please ensure it is installed and in the system's PATH."
    
    except subprocess.TimeoutExpired:
        error_msg = "FFmpeg process timed out after 30 seconds of no output."
        logger.error(f"FFmpeg process for task {task_id} timed out.")
        if proc:
            proc.kill()
        return False, error_msg

    except Exception as e:
        logger.error(f"Exception in blocking runner for task {task_id}: {e!r}", exc_info=True)
        return False, str(e)
    finally:
        # --- 核心修改: 任务结束时清理缓存 ---
        with _progress_lock:
            if task_id in task_progress_cache:
                del task_progress_cache[task_id]


# --- 核心修改：重构后的异步任务包装器 ---
async def run_ffmpeg_process(
    task_id: int, 
    command_args: list, 
    total_duration: float, 
    display_command: str = "", 
    temp_output_path: str = "", 
    final_output_path: str = "",
    final_display_name: str = ""
):
    """
    异步包装器，使用 run_in_executor 将阻塞的 FFmpeg 任务移到后台线程。
    此函数处理所有数据库状态更新。
    """
    db = SessionLocal()
    logger = logging.getLogger("ffmpeg_runner")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)

    try:
        logger.info(f"run_ffmpeg_process: start task_id={task_id}, command={display_command}")
        crud.update_task(db, task_id=task_id, status="processing", progress=0)

        loop = asyncio.get_running_loop()
        
        # --- 核心修改: 不再接收 progress_updates ---
        success, full_stderr = await loop.run_in_executor(
            None,
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
                os.replace(temp_output_path, final_output_path)

                task = crud.get_task(db, task_id)
                new_db_file = None # 初始化
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
                    result_file_id=new_db_file.id if new_db_file else None # 关联结果文件
                )
                logger.info(f"Task {task_id} post-processing finished. Output: {final_output_path}")

            except Exception as e:
                error_msg = f"FFmpeg succeeded, but post-processing failed: {e!r}"
                logger.error(error_msg, exc_info=True)
                crud.update_task(db, task_id=task_id, status="failed", details=error_msg)
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
        else:
            logger.error(f"Task {task_id} blocking process failed. Stderr: {full_stderr}")
            crud.update_task(db, task_id=task_id, status="failed", details=full_stderr)
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
    resolved = await asyncio.get_running_loop().run_in_executor(
        None, reconstruct_file_path, file_path, current_user.id
    )
    if not resolved:
        raise HTTPException(status_code=404, detail="File not found on server")
    file_path = resolved

    def run_ffprobe_sync(path: str) -> Tuple[int, str, str]:
        """在一个独立的线程中执行的、阻塞的 ffprobe 函数"""
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
        raise HTTPException(status_code=500, detail="ffprobe command not found. Please ensure FFmpeg is installed and in the system's PATH.")
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

def construct_ffmpeg_command(input_path: str, output_path: str, params: schemas.ProcessPayload) -> list:
    """
    智能构建 FFmpeg 命令。
    此版本合并了所有逻辑：
    1. 智能纠正与目标容器不兼容的编解码器。
    2. 自动为纯音频格式移除视频流 (-vn)。
    3. 优先尝试为 AV1 视频指定 NVIDIA 硬件解码器 (av1_cuvid)。
    4. 保留 -analyzeduration 和 -probesize 作为后备，以处理一般性文件解析问题。
    """
    # --- 1. 初始化和参数决策 (来自旧 smart_detect_video_params 的逻辑) ---
    
    # 从前端请求中获取初始参数
    video_codec = params.videoCodec
    audio_codec = params.audioCodec
    container = params.container

    # 判断是否为纯音频输出格式
    is_audio_only_output = container in ['mp3', 'flac', 'wav', 'aac', 'ogg']

    # --- 智能纠正视频编解码器 ---
    if not is_audio_only_output and video_codec != 'copy':
        # 为常用视频容器推荐并强制使用兼容的编码器
        if container == 'mp4' and video_codec not in ['libx264', 'libx265']:
            video_codec = 'libx264'  # MP4 最广泛兼容的是 H.264
        elif container == 'mkv' and video_codec not in ['libx264', 'libx265', 'libaom-av1', 'vp9']:
            video_codec = 'libx264'  # MKV 很灵活，但 H.264 是安全的选择
        elif container == 'mov' and video_codec not in ['libx264', 'libx265']:
            video_codec = 'libx264'  # MOV 常用 H.264

    # --- 智能纠正音频编解码器 ---
    if audio_codec != 'copy':
        # 为常用容器推荐并强制使用兼容的编码器
        if container in ['mp4', 'mov'] and audio_codec not in ['aac', 'mp3']:
            audio_codec = 'aac'  # MP4/MOV 标准音频是 AAC
        elif container == 'mkv' and audio_codec not in ['aac', 'mp3', 'opus', 'flac']:
            audio_codec = 'aac'  # 为 MKV 默认 AAC
        # 如果输出容器本身就是一种音频编码，则强制使用对应的编码器
        elif container == 'mp3':
            audio_codec = 'libmp3lame' # 使用高质量 LAME MP3 编码器
        elif container == 'flac':
            audio_codec = 'flac'
        elif container == 'aac':
            audio_codec = 'aac'
        elif container == 'wav':
            audio_codec = 'pcm_s16le' # WAV 通常使用 PCM

    # --- 2. 开始构建命令列表 ---
    command = ["ffmpeg", "-y"]

    # --- 3. 添加输入解码选项 (硬件加速检测等) ---

    # 检测输入视频的编码
    input_codec = detect_video_codec(input_path)

    # 如果是 AV1 编码，优先尝试使用 NVIDIA 硬件解码器
    if input_codec == 'av1':
        logging.getLogger("ffmpeg_runner").info("Detected AV1 input, attempting to use hardware decoder 'av1_cuvid'.")
        command.extend(["-c:v", "av1_cuvid"])

    # 总是添加分析参数，以提高对不标准文件的解析成功率
    command.extend(["-analyzeduration", "20M", "-probesize", "20M"])

    # --- 4. 添加输入、裁剪和流映射 ---

    # 输入文件必须在 seek 参数之前，以实现精确的输出 seek
    command.extend(["-i", input_path])

    # 裁剪开始时间
    if params.startTime > 0:
        command.extend(["-ss", str(params.startTime)])
    
    # 裁剪结束时间
    if params.endTime < params.totalDuration:
        command.extend(["-to", str(params.endTime)])

    # 如果是纯音频输出，则明确告诉 FFmpeg 丢弃视频流
    if is_audio_only_output:
        command.append("-vn")  # -vn (video null) 表示无视频
        command.extend(["-map", "0:a?"]) # 只映射音频流
    else:
        # 否则，映射所有可能的视频和音频流
        command.extend(["-map", "0:v?", "-map", "0:a?"])

    # 修复时间戳
    command.extend(["-fflags", "+genpts", "-avoid_negative_ts", "make_zero"])

    # --- 5. 添加编码选项 ---

    # 视频编码 (仅在不是纯音频输出时添加)
    if not is_audio_only_output:
        if video_codec != "copy":
            command.extend(["-c:v", video_codec])
            # 如果进行了裁剪，强制在剪辑的开头创建一个关键帧，以防止片头卡顿
            if params.startTime > 0 or params.endTime < params.totalDuration:
                command.extend(["-force_key_frames", "expr:eq(n,0)"])

            if params.videoBitrate:
                command.extend(["-b:v", f"{params.videoBitrate}k"])
            if params.resolution:
                command.extend(["-s", f"{params.resolution.width}x{params.resolution.height}"])
        else:
            command.extend(["-c:v", "copy"])

    # 音频编码
    if audio_codec != "copy":
        command.extend(["-c:a", audio_codec])
        if params.audioBitrate:
            command.extend(["-b:a", f"{params.audioBitrate}k"])
    else:
        command.extend(["-c:a", "copy"])

    # --- 6. 添加输出路径 ---
    command.append(output_path)

    return command



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

        # --- 智能构建 FFmpeg 命令 ---
        input_path = os.path.normpath(db_file.filepath)
        
        # 1. 获取不带扩展名的原始文件名和扩展名
        original_filename_base, _ = os.path.splitext(db_file.filename)

        # 2. 构造带有 "_processed" 后缀的显示用目标文件名 (保存在 DB 中作为 filename)
        final_display_name = f"{original_filename_base}_processed.{payload.container}"

        # 3. 确定最终处理完成后在磁盘上将使用的 UUID 文件名（保持扩展名）
        final_disk_filename = f"{uuid.uuid4()}.{payload.container}"
        final_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), final_disk_filename))
        
        # 4. 创建一个临时的、唯一的输出路径，FFmpeg 将先写入这里
        temp_output_filename = f"{uuid.uuid4()}.{payload.container}"
        temp_output_path = os.path.normpath(os.path.join(os.path.dirname(input_path), temp_output_filename))

        # 5. 使用智能函数构建 FFmpeg 命令
        command = construct_ffmpeg_command(input_path, temp_output_path, payload)

        # 构造一个用于显示/存入 DB 的可读命令字符串
        if sys.platform == "win32":
            ffmpeg_command_str = subprocess.list2cmdline(command)
        else:
            ffmpeg_command_str = " ".join(shlex.quote(p) for p in command)

        logging.getLogger("ffmpeg_runner").info(f"Creating task for file_id={file_id} input={input_path} temp_output={temp_output_path} final_output={final_output_path}")
        logging.getLogger("ffmpeg_runner").info(f"FFmpeg command string: {ffmpeg_command_str}")

        # --- 创建数据库任务记录 ---
        task_in = schemas.TaskCreate(
            ffmpeg_command=ffmpeg_command_str,
            source_filename=db_file.filename # 将源文件名存入DB
        )
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
            final_output_path=final_output_path,
            final_display_name=final_display_name,
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
    skip: int = 0,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有处理任务，支持分页"""
    return crud.get_user_tasks(db, owner_id=current_user.id, skip=skip)


@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"])
def delete_task(
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除指定的任务记录"""
    db_task = crud.get_task(db, task_id=task_id)
    if db_task and db_task.owner_id != current_user.id:
        # 如果任务存在但不属于当前用户，则拒绝操作
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this task")
    
    # 如果任务存在且属于用户，则删除
    if db_task:
        crud.delete_task(db, task_id=task_id)
    
    # 如果任务不存在，也直接返回成功，简化客户端逻辑
    return


@app.get("/api/tasks/{task_id}/progress", tags=["Tasks"])
def get_task_progress(
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定任务的实时进度"""
    # 1. (安全) 检查任务是否存在且属于当前用户
    db_task = crud.get_task(db, task_id=task_id)
    if not db_task or db_task.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # 新增：检查任务是否失败
    if db_task.status == 'failed':
        return JSONResponse(content={"progress": -1})

    # 2. 尝试从实时缓存中获取进度
    with _progress_lock:
        progress = task_progress_cache.get(task_id)

    # 3. 如果缓存中没有（例如，任务刚开始或已结束），则从数据库回退
    if progress is None:
        progress = db_task.progress

    return JSONResponse(content={"progress": progress})




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