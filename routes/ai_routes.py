from fastapi import APIRouter
from controllers.ai_controller import (
    generate_questions_service,
    generate_explanation_service,
)

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/generate-questions")
async def generate_questions(body: dict):
    return await generate_questions_service(body)


@router.post("/generate-explanation")
async def generate_explanation(body: dict):
    return await generate_explanation_service(body)
