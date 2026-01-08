from fastapi import APIRouter, Request, Depends
from controllers.pdf_controller import *
from middlewares.auth_middlewares import protect

router = APIRouter(prefix="/api/sessions", tags=["PDF"])

@router.get("/{session_id}/download-pdf")
async def download_pdf(
    session_id: str,
    request: Request,
    user_data=Depends(protect)
):
    return await download_session_pdf(session_id, request)


