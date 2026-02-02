# Files API 主路由
# 此文件将所有文件相关端点组合在一起

from fastapi import APIRouter

from . import upload, download, process, capabilities, delete

router = APIRouter(
    tags=["Files"],
)

# 包含所有子路由
router.include_router(upload.router)
router.include_router(download.router)
router.include_router(process.router)
router.include_router(capabilities.router)
router.include_router(delete.router)
