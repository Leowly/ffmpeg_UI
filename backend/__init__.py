# backend/__init__.py - Backward compatibility shim
# This module re-exports from the new backend.app structure for backward compatibility

# Load .env file from project root before any imports
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from .app import models, crud, main
from .app.core import config, security, database, limiter
from .app.core.deps import get_db, get_current_user, oauth2_scheme

__all__ = [
    "models",
    "crud",
    "main",
    "config",
    "security",
    "database",
    "limiter",
    "get_db",
    "get_current_user",
    "oauth2_scheme",
]
