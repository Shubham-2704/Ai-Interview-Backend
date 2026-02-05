from fastapi import APIRouter, Depends, Request
from controllers.session_controller import *
from middlewares.auth_middlewares import protect
from middlewares.settings_middlewares import check_session_limit

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])

# 🔴 PUT THIS ROUTE FIRST - before any {session_id} routes
@router.get("/check-limit")
async def check_session_limit_route(
    request: Request,
    user = Depends(protect),
):
    """Check if user can create more sessions"""
    limit_info = await check_session_limit(user["id"])
    
    return {
        "success": True,
        "data": limit_info
    }

# 🔴 Then put other specific routes
@router.post("/create")
async def create_session(
    request: Request,
    data: SessionCreate,         
    user = Depends(protect),
):
    return await create_new_session(request, data)

@router.get("/my-sessions")
async def my_sessions(request: Request, user=Depends(protect)):
    return await get_my_sessions(request)

# 🔴 PUT {session_id} ROUTES LAST
@router.get("/{session_id}")
async def session_details(request: Request, session_id: str, user=Depends(protect)):
    return await get_session_by_id(request, session_id)

@router.delete("/{session_id}")
async def delete_session_route(request: Request, session_id: str, user=Depends(protect)):
    return await delete_session(request, session_id)

@router.post("/{session_id}/increment-load-more")
async def increment_load_more_count(
    request: Request,
    session_id: str,
    user = Depends(protect)
):
    return await increment_load_more_counter(request, session_id)
