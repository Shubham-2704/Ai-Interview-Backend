from controllers.session_controller import *
from models.session_model import *
from routes.upload_routes import *
from fastapi import APIRouter, Depends, Request
from middlewares.auth_middlewares import protect

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])

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

@router.get("/{session_id}")
async def session_details(request: Request, session_id: str, user=Depends(protect)):
    return await get_session_by_id(request, session_id)

@router.delete("/{session_id}")
async def delete_session_route(request: Request, session_id: str, user=Depends(protect)):
    return await delete_session(request, session_id)