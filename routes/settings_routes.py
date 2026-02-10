from fastapi import APIRouter, Depends, Request, HTTPException
from controllers.settings_controller import get_system_settings, update_system_settings, get_tavily_api_usage
from middlewares.auth_middlewares import protect

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("/sessions")
async def get_settings(
    request: Request,
    current_user: dict = Depends(protect)
):
    """Get system settings (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    settings = await get_system_settings()
    return {
        "success": True,
        "settings": settings
    }

@router.put("/sessions")
async def update_settings(
    request: Request,
    data: dict,
    current_user: dict = Depends(protect)
):
    """Update system settings (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await update_system_settings(data.get("settings", {}))
    return result

# NEW PUBLIC ROUTE - No authentication required
@router.get("/public/questions-count")
async def get_public_questions_count():
    """Get all public settings"""
    settings = await get_system_settings()
    
    return {
        "success": True,
        "number_of_questions": settings.get("number_of_questions", 10),
        "load_more_questions": settings.get("load_more_questions", 5),
        "max_load_more_clicks": settings.get("max_load_more_clicks", 3),
        # Add ONLY these two resources settings
        "max_study_materials_per_session": settings.get("max_study_materials_per_session", 10),
        "study_materials_refresh_hours": settings.get("study_materials_refresh_hours", 24),
    }

@router.get("/tavily-usage")
async def get_tavily_usage(
    request: Request,
    current_user: dict = Depends(protect)
):
    """Get Tavily API usage and credit balance (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    usage_data = await get_tavily_api_usage()
    return {
        "success": True,
        "data": usage_data
    }

# In settings_routes.py
@router.get("/public/general")
async def get_public_general_settings():
    """Get general settings (no authentication required)"""
    try:
        settings = await get_system_settings()
        return {
            "success": True,
            "allow_registration": settings.get("allow_registration", True),
            "maintenance_mode": settings.get("maintenance_mode", False),
        }
    except Exception as e:
        print(f"Error getting public settings: {e}")
        return {
            "success": False,
            "allow_registration": True,
            "maintenance_mode": False,
        }