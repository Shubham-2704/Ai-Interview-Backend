from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Query
from controllers.admin_controller import (
    get_dashboard_stats,
    get_admin_users_list,
    get_admin_user_details,
    admin_update_user,
    admin_delete_user,
    get_sessions_stats,
    get_admin_sessions_list,
    get_user_stats_endpoint,  # ADD THIS IMPORT
    admin_create_user,         # ADD THIS IMPORT
    admin_delete_session
)
from models.admin_model import DateRangeRequest
from middlewares.auth_middlewares import protect

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# ---------- Dashboard Routes ----------
@router.get("/dashboard/stats")
async def dashboard_stats(
    request: Request,
    period: str = Query("7d", description="Time period: 7d, 30d, 90d, year"),
    current_user: dict = Depends(protect)
):
    """Get dashboard statistics"""
    date_range = DateRangeRequest(period=period)
    return await get_dashboard_stats(request, date_range, current_user)

# ---------- Users Management Routes ----------
# IMPORTANT: Specific routes must come BEFORE parameterized routes
@router.get("/users/stats")  # ADD THIS - MUST BE BEFORE /users/{user_id}
async def admin_user_stats(
    request: Request,
    current_user: dict = Depends(protect)
):
    """Get user statistics"""
    return await get_user_stats_endpoint(request, current_user)

@router.get("/users")
async def admin_get_users(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    role: str = Query("all"),
    status: str = Query("all"),
    current_user: dict = Depends(protect)
):
    """Get users list with filtering and pagination"""
    return await get_admin_users_list(request, page, limit, search, role, status, current_user)

@router.post("/users")  # ADD THIS - MUST BE BEFORE /users/{user_id}
async def admin_create_user_route(
    request: Request,
    data: dict,
    current_user: dict = Depends(protect)
):
    """Create new user (admin only)"""
    return await admin_create_user(request, data, current_user)

# Parameterized routes MUST COME AFTER specific routes
@router.get("/users/{user_id}")
async def admin_get_user_details(
    request: Request,
    user_id: str,
    current_user: dict = Depends(protect)
):
    """Get detailed user information"""
    return await get_admin_user_details(request, user_id, current_user)

@router.put("/users/{user_id}")
async def admin_update_user_route(
    request: Request,
    user_id: str,
    data: dict,
    current_user: dict = Depends(protect)
):
    """Update user information (admin only)"""
    return await admin_update_user(request, user_id, data, current_user)

@router.delete("/users/{user_id}")
async def admin_delete_user_route(
    request: Request,
    user_id: str,
    current_user: dict = Depends(protect)
):
    """Delete user and all associated data"""
    return await admin_delete_user(request, user_id, current_user)

# ---------- Sessions Routes ----------
@router.get("/sessions")
async def admin_get_sessions(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    status: str = Query("all"),
    current_user: dict = Depends(protect)
):
    """Get all sessions with filtering"""
    return await get_admin_sessions_list(request, page, limit, search, status, current_user)

@router.get("/sessions/stats")
async def admin_sessions_stats(
    request: Request,
    period: str = Query("7d", description="Time period: 7d, 30d, 90d"),
    current_user: dict = Depends(protect)
):
    """Get sessions statistics"""
    date_range = DateRangeRequest(period=period)
    return await get_sessions_stats(request, date_range, current_user)

# ---------- Analytics Route ----------
@router.get("/analytics")
async def admin_analytics(
    request: Request,
    current_user: dict = Depends(protect)
):
    """Get comprehensive analytics data"""
    return {
        "status": "success",
        "message": "Analytics endpoint - implement detailed analytics here",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ---------- Health Check ----------
@router.get("/health")
async def admin_health_check():
    """Admin API health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "admin-api"
    }

@router.delete("/sessions/{session_id}")
async def admin_delete_session_route(
    request: Request,
    session_id: str,
    current_user: dict = Depends(protect)
):
    """Delete session (admin only)"""
    return await admin_delete_session(request, session_id, current_user)
