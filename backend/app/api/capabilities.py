# 系统能力检测模块

import asyncio
from fastapi import APIRouter, Depends, Query

from ..models import models
from ..schemas import schemas
from ..core.deps import get_current_user
from ..services.hw_accel import detect_hardware_encoder

router = APIRouter(
    tags=["Files"],
)

SIMULATED_HW_TYPES = {
    "nvidia": "nvidia",
    "intel": "intel",
    "amd": "amd",
    "vaapi": "vaapi",
    "apple": "apple",
    "cpu": None,
}


@router.get("/capabilities", response_model=schemas.SystemCapabilities)
async def get_system_capabilities(
    current_user: models.User = Depends(get_current_user),
    simulate: str | None = Query(
        None, description="模拟硬件类型: nvidia, intel, amd, vaapi, apple, cpu"
    ),
):
    if simulate and simulate in SIMULATED_HW_TYPES:
        hw_type = SIMULATED_HW_TYPES[simulate]
        return schemas.SystemCapabilities(
            has_hardware_acceleration=bool(hw_type), hardware_type=hw_type
        )

    hw_type = await asyncio.get_running_loop().run_in_executor(
        None, detect_hardware_encoder
    )
    return schemas.SystemCapabilities(
        has_hardware_acceleration=bool(hw_type), hardware_type=hw_type
    )
