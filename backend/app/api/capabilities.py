# 系统能力检测模块

import asyncio
from fastapi import APIRouter, Depends

from ..models import models
from ..schemas import schemas
from ..core.deps import get_current_user
from .process import detect_hardware_encoder

router = APIRouter(
    tags=["Files"],
)


@router.get("/capabilities", response_model=schemas.SystemCapabilities)
async def get_system_capabilities(
    current_user: models.User = Depends(get_current_user),
):
    hw_type = await asyncio.get_running_loop().run_in_executor(
        None, detect_hardware_encoder
    )
    return schemas.SystemCapabilities(
        has_hardware_acceleration=bool(hw_type), hardware_type=hw_type
    )
