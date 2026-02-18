import asyncio
from fastapi import APIRouter, Depends

from ..models import models
from ..schemas import schemas
from ..core.deps import get_current_user
from ..services.hw_accel import detect_hardware_encoder

router = APIRouter(
    tags=["Files"],
)

DEBUG_HW_TYPE: str | None = None  # 可设置为 "cpu", "nvidia", "amd", "intel" , "apple" , "vaapi"等进行调试，或 None 进行自动检测


@router.get("/capabilities", response_model=schemas.SystemCapabilities)
async def get_system_capabilities(
    current_user: models.User = Depends(get_current_user),
):
    if DEBUG_HW_TYPE is not None:
        hw_type = DEBUG_HW_TYPE if DEBUG_HW_TYPE != "cpu" else None
        return schemas.SystemCapabilities(
            has_hardware_acceleration=bool(hw_type), hardware_type=hw_type
        )

    hw_type = await asyncio.get_running_loop().run_in_executor(
        None, detect_hardware_encoder
    )
    return schemas.SystemCapabilities(
        has_hardware_acceleration=bool(hw_type), hardware_type=hw_type
    )
