# main.py - FastAPI app entry point
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import crud, models, schemas, security
from .database import SessionLocal, engine
from typing import cast

# This line creates the database tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFmpeg UI Backend",
    description="API for handling user authentication and FFmpeg processing tasks.",
    version="1.0.0",
)

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


@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint providing a welcome message."""
    return {"message": "Welcome to the FFmpeg UI Backend"}