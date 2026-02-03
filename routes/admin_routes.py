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
    get_user_stats_endpoint,
    admin_create_user,
    admin_delete_session,
    get_admin_session_details,
    get_admin_session_questions,
    get_admin_session_study_materials,
    get_admin_study_materials_by_question,
    get_user_quiz_stats,
    get_admin_session_quizzes,
    get_admin_quiz_details,
    get_quiz_results_admin,
)
from models.admin_model import DateRangeRequest, AdminCreateUserRequest
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
@router.post("/users")
async def admin_create_user_route(
    request: Request,
    data: AdminCreateUserRequest,
    current_user: dict = Depends(protect)
):
    """Create new user (admin only)"""
    return await admin_create_user(request, data, current_user)

@router.get("/users/stats")
async def admin_users_stats(
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

@router.delete("/sessions/{session_id}")
async def admin_delete_session_route(
    request: Request,
    session_id: str,
    current_user: dict = Depends(protect)
):
    """Delete session (admin only)"""
    return await admin_delete_session(request, session_id, current_user)

# ---------- Session Detail Routes ----------
@router.get("/sessions/{session_id}")
async def admin_get_session_details(
    request: Request,
    session_id: str,
    current_user: dict = Depends(protect)
):
    """Get detailed session information"""
    return await get_admin_session_details(request, session_id, current_user)

@router.get("/sessions/{session_id}/questions")
async def admin_get_session_questions(
    request: Request,
    session_id: str,
    current_user: dict = Depends(protect)
):
    """Get questions for a specific session"""
    return await get_admin_session_questions(request, session_id, current_user)

@router.get("/sessions/{session_id}/study-materials")
async def admin_get_session_study_materials(
    request: Request,
    session_id: str,
    current_user: dict = Depends(protect)
):
    """Get study materials for a specific session"""
    return await get_admin_session_study_materials(request, session_id, current_user)

@router.get("/sessions/{session_id}/quizzes")
async def admin_get_session_quizzes(
    request: Request,
    session_id: str,
    current_user: dict = Depends(protect)
):
    """Get quizzes for a specific session"""
    return await get_admin_session_quizzes(request, session_id, current_user)

# ---------- Study Materials Routes ----------
@router.get("/study-materials/question/{question_id}")
async def admin_get_study_materials_by_question(
    request: Request,
    question_id: str,
    session_id: str = Query(None, description="Optional session ID filter"),
    current_user: dict = Depends(protect)
):
    """Get study materials for a specific question"""
    return await get_admin_study_materials_by_question(request, question_id, session_id, current_user)

# ---------- User Quiz Statistics Route ----------
@router.get("/users/{user_id}/quiz-stats")
async def admin_get_user_quiz_stats(
    request: Request,
    user_id: str,
    current_user: dict = Depends(protect)
):
    """Get quiz statistics for a specific user"""
    return await get_user_quiz_stats(request, user_id, current_user)

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

@router.get("/quizzes/{quiz_id}")
async def admin_get_quiz_details(
    request: Request,
    quiz_id: str,
    current_user: dict = Depends(protect)
):
    """Get detailed quiz results"""
    return await get_quiz_results_admin(request, quiz_id, current_user)

@router.get("/quizzes/{quiz_id}")
async def admin_get_quiz_details(
    request: Request,
    quiz_id: str,
    current_user: dict = Depends(protect)
):
    """Get detailed quiz results"""
    return await get_admin_quiz_details(request, quiz_id, current_user)


