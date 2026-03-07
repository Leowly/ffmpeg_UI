"""
runtime/run_backend.py - Backend Startup Script

This module handles platform-specific configuration and starts the FastAPI backend.
Responsibilities:
- Platform detection (Windows/Linux/Mac)
- Event loop policy configuration
- Uvicorn server startup with proper parameters
"""

import uvicorn
import asyncio
import sys
from pathlib import Path

# Project root directory (where run.py and backend/ are located)
project_root = Path(__file__).parent.parent


def setup_event_loop():
    """Configure event loop policy based on platform."""
    if sys.platform == "win32":
        print(">>> [runtime] Setting WindowsProactorEventLoopPolicy for Uvicorn...")
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print(">>> [runtime] Policy successfully set.")
    else:
        print(f">>> [runtime] Running on {sys.platform} - no special policy needed")


def start_backend(
    host: str = "127.0.0.1", port: int = 8000, reload: bool | None = None
):
    """
    Start the FastAPI backend server.

    Args:
        host: Server host address
        port: Server port
        reload: Override reload setting from config if provided
    """
    setup_event_loop()

    # Import config to get reload setting
    from backend.app.core.config import RELOAD as config_reload

    # Use parameter if provided, otherwise use config value
    use_reload = reload if reload is not None else config_reload

    print(f">>> [runtime] Starting Uvicorn server at {host}:{port}...")
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=use_reload,
        app_dir=str(project_root),
    )


if __name__ == "__main__":
    start_backend()
