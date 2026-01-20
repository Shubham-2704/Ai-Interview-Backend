from fastapi import APIRouter, Request, Depends, HTTPException, Body
from typing import Dict
from utils.backend_tracking import track_event
from middlewares.auth_middlewares import protect
import os

router = APIRouter(prefix="/api/track", tags=["Tracking"])

@router.post("/event")
async def track_custom_event(
    request: Request,
    event_data: Dict = Body(...),  # Accept JSON body
    current_user: dict = Depends(protect)
):
    """Track custom event from frontend"""
    
    try:
        session_id = request.cookies.get("session_id") or "unknown"
        
        await track_event(
            user_id=current_user.get("id"),
            session_id=session_id,
            event_name=event_data.get("event_name"),
            event_category=event_data.get("event_category", "general"),
            event_label=event_data.get("event_label"),
            event_value=event_data.get("event_value"),
            page_path=event_data.get("page_path", request.headers.get("referer", "/"))
        )
        
        return {"status": "success", "message": "Event tracked"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/pageview")
async def track_custom_pageview(
    request: Request,
    page_data: Dict = Body(...),  # Accept JSON body
    current_user: dict = Depends(protect)
):
    """Track page view from frontend"""
    
    try:
        from utils.backend_tracking import track_page_view
        
        session_id = request.cookies.get("session_id") or "unknown"
        
        await track_page_view(
            request=request,
            user_id=current_user.get("id"),
            session_id=session_id,
            page_path=page_data.get("page_path", "/"),
            page_title=page_data.get("page_title", "Unknown Page")
        )
        
        return {"status": "success", "message": "Page view tracked"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/health")
async def tracking_health():
    """Check if tracking is working"""
    return {
        "status": "healthy",
        "tracking_enabled": True,
        "ga4_configured": bool(os.getenv("GA4_MEASUREMENT_ID") and os.getenv("GA4_MEASUREMENT_ID"))
    }


