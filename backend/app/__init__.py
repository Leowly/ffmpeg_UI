# backend/app/__init__.py
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from app import models
from app import crud

__all__ = ["models", "crud"]
