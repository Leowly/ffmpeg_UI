# backend/app/schemas/file.py - File schemas
from typing import List, Optional
from pydantic import BaseModel


class FileBase(BaseModel):
    filename: str
    filepath: str
    status: str = "uploaded"


class FileCreate(FileBase):
    pass


class File(FileBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True


# --- Frontend Specific File Response Schema ---
class FileResponseInner(BaseModel):
    file_id: str
    original_name: str
    temp_path: str


class FileResponseForFrontend(BaseModel):
    uid: str
    id: str
    name: str
    status: str
    size: int
    response: FileResponseInner

    class Config:
        from_attributes = True
