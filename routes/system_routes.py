from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from controllers.system_controller import *
from middlewares.auth_middlewares import protect

router = APIRouter(prefix="/api/admin", tags=["System"])

@router.get("/system/status")
async def admin_system_status(
    request: Request,
    current_user: dict = Depends(protect)
):
    """Get detailed system status and health metrics"""
    return await get_system_status()

@router.get("/system/metrics")
async def admin_system_metrics(
    request: Request,
    current_user: dict = Depends(protect)
):
    """Get comprehensive system metrics for monitoring dashboard"""
    return await get_real_system_status()
