# main.py - FastAPI app entry point
import os
import uuid
import subprocess
import json
import asyncio
from typing import cast, List

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
UPLOAD_DIRECTORY = "./backend/uploads"
# Ensure the upload directory exists
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# --- Background Task Runner ---
async def run_ffmpeg_process(task_id: int, command: str, db_path: str):
    """
    一个在后台运行 ffmpeg 命令的函数。
    注意：这个函数在一个独立的线程中运行，因此需要它自己的数据库会话。
    """
    # 为后台任务创建新的数据库会话
    from .database import SessionLocal as TaskSessionLocal
    db = TaskSessionLocal()
    try:
        # 1. 更新任务状态为 "processing"
        crud.update_task(db, task_id=task_id, status="processing")

        # 2. 执行 ffmpeg 命令
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        # 3. 根据结果更新任务状态
        if proc.returncode == 0:
            crud.update_task(db, task_id=task_id, status="completed", details=stdout.decode())
        else:
            error_details = stderr.decode()
            crud.update_task(db, task_id=task_id, status="failed", details=error_details)
    except Exception as e:
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
    """
    created_tasks = []
    # 为这个请求创建一个唯一的输出子目录
    output_subdir = os.path.join(UPLOAD_DIRECTORY, str(current_user.id), "processed", str(uuid.uuid4()))
    os.makedirs(output_subdir, exist_ok=True)

    for file_id_str in payload.files:
        try:
            file_id = int(file_id_str)
        except ValueError:
            # 在循环中跳过无效ID，或收集错误信息
            continue

        db_file = crud.get_file_by_id(db, file_id=file_id)
        if not db_file or db_file.owner_id != current_user.id:
            continue # 跳过不属于此用户的文

        # --- 动态构建 FFmpeg 命令 ---
        input_path = db_file.filepath
        original_filename = os.path.splitext(db_file.filename)[0]
        output_filename = f"{original_filename}_processed.{payload.container}"
        output_path = os.path.join(output_subdir, output_filename)

        command = ["ffmpeg", "-i", input_path]

        # 1. 时间裁剪
        if payload.startTime > 0 or payload.endTime < payload.totalDuration:
            command.extend(["-ss", str(payload.startTime), "-to", str(payload.endTime)])

        # 2. 视频编码
        command.extend(["-c:v", payload.videoCodec])
        if payload.videoCodec != 'copy':
            if payload.videoBitrate:
                command.extend(["-b:v", f"{payload.videoBitrate}k"])
            if payload.resolution:
                command.extend(["-s", f"{payload.resolution.width}x{payload.resolution.height}"])
        
        # 3. 音频编码
        command.extend(["-c:a", payload.audioCodec])
        if payload.audioCodec != 'copy' and payload.audioBitrate:
            command.extend(["-b:a", f"{payload.audioBitrate}k"])

        # 4. 输出路径
        command.append(output_path)

        ffmpeg_command_str = " ".join(command)

        # --- 创建数据库任务记录 ---
        task_in = schemas.TaskCreate(ffmpeg_command=ffmpeg_command_str, output_path=output_path)
        db_task = crud.create_task(db=db, task=task_in, owner_id=current_user.id, output_path=output_path)

        # --- 添加到后台任务队列 ---
        background_tasks.add_task(run_ffmpeg_process, db_task.id, ffmpeg_command_str, db_path=DB_PATH)

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


@app.get("/api/download-task/{task_id}", tags=["Tasks"])
def download_task_output(
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载已完成任务的输出文件"""
    task = db.query(models.ProcessingTask).filter(models.ProcessingTask.id == task_id).first()

    if not task or task.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found or not owned by user")

    if task.status != 'completed':
        raise HTTPException(status_code=400, detail="Task is not completed yet")

    if not task.output_path or not os.path.exists(task.output_path):
        raise HTTPException(status_code=404, detail="Output file not found on server")

    # 从输出路径中提取原始文件名作为下载时的文件名
    output_filename = os.path.basename(task.output_path)
    return FileResponse(path=task.output_path, filename=output_filename, media_type="application/octet-stream")


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

        file_location = os.path.join(user_upload_directory, unique_filename)

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