from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from controllers.analytics_controller import *
from middlewares.auth_middlewares import protect

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/dashboard")
async def get_analytics_dashboard(
    time_range: str = Query("7d", description="Time range: 24h, 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """
    Get complete analytics dashboard
    - Overview metrics
    - Real-time data
    - Acquisition channels
    - Page performance
    - Geographic data
    - Device analytics
    - Events tracking
    """
    try:
        result = await get_dashboard_data(time_range)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/overview")
async def get_overview_analytics(
    time_range: str = Query("7d", description="Time range: 24h, 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """Get overview metrics (users, sessions, pageviews)"""
    try:
        return await get_overview_data(time_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/realtime")
async def get_realtime_analytics(
    current_user: dict = Depends(protect)
):
    """Get real-time analytics"""
    try:
        return await get_realtime_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/acquisition")
async def get_acquisition_analytics(
    time_range: str = Query("30d", description="Time range: 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """Get user acquisition channels"""
    try:
        return await get_acquisition_data(time_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pages")
async def get_pages_analytics(
    time_range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """Get page performance"""
    try:
        return await get_pages_data(time_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/geographic")
async def get_geographic_analytics(
    time_range: str = Query("30d", description="Time range: 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """Get geographic distribution"""
    try:
        return await get_geographic_data(time_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/devices")
async def get_devices_analytics(
    time_range: str = Query("30d", description="Time range: 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """Get device and browser analytics"""
    try:
        return await get_devices_data(time_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events")
async def get_events_analytics(
    time_range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """Get events analytics"""
    try:
        return await get_events_data(time_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def analytics_health(
    current_user: dict = Depends(protect)
):
    """Check analytics API health"""
    return {
        "status": "healthy",
        "service": "analytics",
        "endpoints": [
            "/api/analytics/dashboard",
            "/api/analytics/overview",
            "/api/analytics/realtime",
            "/api/analytics/acquisition",
            "/api/analytics/pages",
            "/api/analytics/geographic",
            "/api/analytics/devices",
            "/api/analytics/events"
        ]
    }
