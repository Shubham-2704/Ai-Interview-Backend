from fastapi import APIRouter
from controllers.ai_controller import *
from controllers.auth_controller import *

router = APIRouter(prefix="/api/ai", tags=["AI"])

@router.post("/generate-questions")
async def generate_questions(
    body: dict,
    request: Request,
    user_data=Depends(protect)
):
    user_id = request.state.user["id"]
    return await generate_questions_service(body, user_id)


@router.post("/generate-explanation")
async def generate_explanation(
    body: dict,
    request: Request,
    user_data=Depends(protect)
):
    user_id = request.state.user["id"]
    return await generate_explanation_service(body, user_id)


@router.post("/api-key")
async def save_gemini_key(
    payload : UpdateGeminiKey,
    request: Request,
    user_data=Depends(protect)
):
    return await save_key(payload, request)


@router.delete("/api-key")
async def delete_gemini_key(
    request: Request,
    user_data=Depends(protect)
):
    return await delete_key(request)

@router.post("/followup-chat")
async def followup_chat(
    body: dict,
    request: Request,
    user_data = Depends(protect)
):
    user_id = request.state.user["id"]
    return await followup_chat_service(body, user_id)
