from fastapi import APIRouter, Depends
from middlewares.auth_middlewares import protect

from controllers.question_controller import (
    add_questions_to_session_service,
    toggle_pin_question_service,
    update_question_note_service,
)

from models.question_model import (
    AddQuestionsRequest,
    UpdateNoteRequest,
)

router = APIRouter(prefix="/api/questions", tags=["Questions"])


@router.post("/add")
async def add_questions_to_session(
    body: AddQuestionsRequest,
    user = Depends(protect)
):
    return await add_questions_to_session_service(body, user)


@router.post("/{id}/pin")
async def toggle_pin_question(id: str, user = Depends(protect)):
    return await toggle_pin_question_service(id)


@router.post("/{id}/note")
async def update_question_note(
    id: str,
    body: UpdateNoteRequest,
    user = Depends(protect)
):
    return await update_question_note_service(id, body)

