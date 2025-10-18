# main.py - FastAPI app entry point
import os
import uuid
import subprocess
import json
import asyncio
import logging
import shlex
import sys
from typing import cast, List

if sys.platform == "win32":
    print(">>> Gemini: Running on Windows. Attempting to set Proactor event loop policy...")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print(">>> Gemini: Policy set to Proactor.")
else:
    print(f">>> Gemini: Running on non-Windows platform ({sys.platform}), no policy change needed.")


from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from . import crud, models, schemas, security
from .database import SessionLocal, engine, DB_PATH

# This line creates the database tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:5173",  # Frontend development server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
UPLOAD_DIRECTORY = "./backend/workspaces"
# Ensure the upload directory exists
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

async def run_ffmpeg_process(
    task_id: int, 
    command_args: list, 
    total_duration: float, 
    db_path: str, 
    display_command: str = "", 
    temp_output_path: str = "", 
    final_output_path: str = ""
):
    """
    一个在后台运行 ffmpeg 命令的函数。
    它将输出写入一个临时文件，成功后，将其重命名为最终文件名，
    并为这个新文件在数据库中创建一条记录。
    """
    from .database import SessionLocal as TaskSessionLocal
    db = TaskSessionLocal()

    logger = logging.getLogger("ffmpeg_runner")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)

    try:
        print(f"run_ffmpeg_process: start task_id={task_id} display_command={display_command}")
        logger.info(f"run_ffmpeg_process: start task_id={task_id}")
        
        crud.update_task(db, task_id=task_id, status="processing")

        import re
        time_re = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        proc = await asyncio.create_subprocess_exec(
            *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_root
        )

        if proc is None:
            raise RuntimeError("Failed to create subprocess")

        stderr_lines: list[str] = []
        last_progress = -1

        # 实时读取和解析 stderr
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            s = line.decode(errors='ignore')
            logger.info(s.strip())
            stderr_lines.append(s)
            m = time_re.search(s)
            if m:
                try:
                    h, mm = int(m.group(1)), int(m.group(2))
                    ss = float(m.group(3))
                    elapsed = h * 3600 + mm * 60 + ss
                    if total_duration and total_duration > 0:
                        progress = int(min(100, (elapsed / total_duration) * 100))
                        if progress != last_progress:
                            crud.update_task(db, task_id=task_id, status="processing", progress=progress, details=''.join(stderr_lines[-20:]))
                            last_progress = progress
                except Exception:
                    pass

        stdout, stderr = await proc.communicate()
        full_stderr = ''.join(stderr_lines) + (stderr.decode(errors='ignore') if stderr else '')

        # --- 根据结果执行后处理 ---
        if proc.returncode == 0:
            # 成功：重命名文件，并在数据库中创建新文件记录
            try:
                # 1. 将临时文件重命名为最终的目标文件名
                #    如果最终文件已存在，先删除它，以确保重命名成功
                if os.path.exists(final_output_path):
                    os.remove(final_output_path)
                os.rename(temp_output_path, final_output_path)
                
                # 2. 在数据库中为这个新处理好的文件创建一条记录
                from . import schemas, crud
                task = crud.get_task(db, task_id)
                if task:
                    new_file_schema = schemas.FileCreate(
                        filename=os.path.basename(final_output_path),
                        filepath=final_output_path,
                        status="processed"  # 使用一个新状态来标识
                    )
                    crud.create_user_file(db=db, file=new_file_schema, user_id=task.owner_id)
                
                # 3. 更新任务状态为 "completed"
                crud.update_task(db, task_id=task_id, status="completed", details=full_stderr or stdout.decode(errors='ignore'), progress=100)
                logger.info(f"Task {task_id} completed successfully. Output at: {final_output_path}")

            except Exception as e:
                # 如果重命名或数据库操作失败，这是一个严重错误
                error_msg = f"FFmpeg processing succeeded, but post-processing failed: {e!r}"
                logger.error(error_msg)
                crud.update_task(db, task_id=task_id, status="failed", details=error_msg)
                # 尝试删除临时文件，避免留存垃圾文件
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
        else:
            # 失败：更新任务状态，并删除无用的临时文件
            crud.update_task(db, task_id=task_id, status="failed", details=full_stderr, progress=0)
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            logger.error(f"Task {task_id} failed. FFmpeg stderr: {full_stderr}")

    except Exception as e:
        logger.error(f"An exception occurred in run_ffmpeg_process for task {task_id}: {e!r}", exc_info=True)
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
def get_file_info(
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

    if not os.path.exists(file_path):
        # If the file is not found at the stored path, try to reconstruct it
        # This handles cases where files were uploaded before user-specific directories were implemented
        expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        # Extract the unique filename from the stored filepath
        unique_filename = os.path.basename(file_path)
        reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)

        if os.path.exists(reconstructed_file_path):
            file_path = reconstructed_file_path
            # Optionally, update the database with the new path for future consistency
            # crud.update_file_path(db, db_file.id, reconstructed_file_path)
        else:
            raise HTTPException(status_code=404, detail="File not found on server")

    try:
        command = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"ffprobe error: {e.stderr}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Could not parse ffprobe output")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/files", response_model=List[schemas.FileResponseForFrontend], tags=["Files"])
def read_user_files(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_files = crud.get_user_files(db, user_id=current_user.id)
    response_files = []
    for db_file in db_files:
        current_file_path = db_file.filepath
        resolved_file_path = None # Initialize to None

        if os.path.exists(current_file_path):
            resolved_file_path = current_file_path
        else:
            # Try to reconstruct
            expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
            unique_filename = os.path.basename(current_file_path)
            reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)

            if os.path.exists(reconstructed_file_path):
                resolved_file_path = reconstructed_file_path
                # Optionally, update the database with the new path for future consistency
                # crud.update_file_path(db, db_file.id, reconstructed_file_path)

        if resolved_file_path: # Only proceed if a valid path was found
            file_size = os.path.getsize(resolved_file_path)
            response_files.append(schemas.FileResponseForFrontend(
                uid=str(db_file.id),
                id=str(db_file.id),
                name=db_file.filename,
                status=db_file.status,
                size=file_size,
                response=schemas.FileResponseInner(
                    file_id=str(db_file.id),
                    original_name=db_file.filename,
                    temp_path=resolved_file_path # Use the resolved path here
                )
            ))

    return response_files


@app.get("/api/download-file/{file_id}", tags=["Files"])
def download_file(
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
    if not os.path.exists(file_path):
        # If the file is not found at the stored path, try to reconstruct it
        # This handles cases where files were uploaded before user-specific directories were implemented
        expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        # Extract the unique filename from the stored filepath
        unique_filename = os.path.basename(file_path)
        reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)

        if os.path.exists(reconstructed_file_path):
            file_path = reconstructed_file_path
            # Optionally, update the database with the new path for future consistency
            # crud.update_file_path(db, db_file.id, reconstructed_file_path)
        else:
            raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(path=file_path, filename=db_file.filename, media_type="application/octet-stream")

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
            db_path=DB_PATH, 
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
def delete_user_file(
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
    if not os.path.exists(file_path):
        # If the file is not found at the stored path, try to reconstruct it
        expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(current_user.id))
        unique_filename = os.path.basename(file_path)
        reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)

        if os.path.exists(reconstructed_file_path):
            file_path = reconstructed_file_path

    if os.path.exists(file_path):
        os.remove(file_path)

    # Delete database record
    crud.delete_file(db, file_id=file_id)

    return {"message": f"File {filename} deleted successfully"}


@app.post("/api/upload", response_model=schemas.FileResponseForFrontend, tags=["Files"])
def upload_file(
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

        with open(file_location, "wb") as buffer:
            buffer.write(file.file.read())

        # Get file size after writing
        file_size = os.path.getsize(file_location)

        # Create a database entry for the uploaded file
        db_file = crud.create_user_file(
            db=db,
            file=schemas.FileCreate(
                filename=file.filename,
                filepath=file_location,
                status="uploaded"
            ),
            user_id=current_user.id
        )

        # Construct response to match frontend's UserFile interface
        return schemas.FileResponseForFrontend(
            uid=str(db_file.id),
            id=str(db_file.id),
            name=db_file.filename,
            status="done", # Assuming 'done' after successful upload and DB entry
            size=file_size,
            response=schemas.FileResponseInner(
                file_id=str(db_file.id),
                original_name=db_file.filename,
                temp_path=db_file.filepath
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not upload file: {e}")


@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint providing a welcome message."""
    return {"message": "Welcome to the FFmpeg UI Backend"}