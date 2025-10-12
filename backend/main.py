# main.py - FastAPI app entry point
import os
import uuid
import subprocess
import json
from typing import cast, List

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from . import crud, models, schemas, security
from .database import SessionLocal, engine

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
UPLOAD_DIRECTORY = "./backend//uploads"
# Ensure the upload directory exists
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

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


@app.post("/api/process", response_model=List[schemas.File], tags=["Files"])
def process_files(
    payload: schemas.ProcessPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    processed_files = []
    for file_id_str in payload.files:
        try:
            file_id = int(file_id_str)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid file ID format: {file_id_str}")

        db_file = crud.get_file_by_id(db, file_id=file_id)
        if not db_file or db_file.owner_id != current_user.id:
            # Skip or raise error for files not found or not owned
            # For now, we'll raise an error for simplicity
            raise HTTPException(status_code=404, detail=f"File {file_id_str} not found or not owned by user")

        # Simulate FFmpeg processing
        crud.update_file_status(db, file_id, "processing")
        # In a real application, this would involve calling FFmpeg and waiting for it to complete
        # For now, we'll just mark it as completed immediately
        updated_file = crud.update_file_status(db, file_id, "completed")
        if updated_file:
            processed_files.append(updated_file)
    return processed_files


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