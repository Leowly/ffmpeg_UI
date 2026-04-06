# backend/app/crud/__init__.py
from types import SimpleNamespace
from app.crud.crud_user import get_user_by_username, create_user
from app.crud.crud_file import (
    get_file_by_id,
    get_user_files,
    create_user_file,
    delete_file,
)
from app.crud.crud_task import (
    create_task,
    update_task,
    delete_task,
    get_task,
    get_user_tasks,
)

crud = SimpleNamespace(
    get_user_by_username=get_user_by_username,
    create_user=create_user,
    get_file_by_id=get_file_by_id,
    get_user_files=get_user_files,
    create_user_file=create_user_file,
    delete_file=delete_file,
    get_user_tasks=get_user_tasks,
    get_task=get_task,
    create_task=create_task,
    update_task=update_task,
    delete_task=delete_task,
)

__all__ = [
    "get_user_by_username",
    "create_user",
    "get_file_by_id",
    "get_user_files",
    "create_user_file",
    "create_task",
    "update_task",
    "delete_task",
    "get_task",
    "get_user_tasks",
    "delete_file",
    "crud",
]
