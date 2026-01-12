from fastapi import APIRouter, Depends, Request
from middlewares.auth_middlewares import protect
from controllers.study_material_controller import (
    get_or_create_study_materials,
    get_study_materials_by_question,
    get_study_materials_by_session,
    refresh_study_materials,
    delete_study_materials
)
from models.study_material_model import StudyMaterialRequest

router = APIRouter(prefix="/api/study-materials", tags=["Study Materials"])

@router.post("/question/{question_id}")
async def generate_study_materials_for_question(
    request: Request,
    question_id: str,
    data: StudyMaterialRequest,
    user = Depends(protect)
):
    return await get_or_create_study_materials(request, question_id, data, user)

@router.get("/question/{question_id}")
async def get_materials_for_question(
    request: Request,
    question_id: str,
    user = Depends(protect)
):
    return await get_study_materials_by_question(request, question_id, user)

@router.get("/session/{session_id}")
async def get_materials_for_session(
    request: Request,
    session_id: str,
    user = Depends(protect)
):
    return await get_study_materials_by_session(request, session_id, user)

@router.post("/{material_id}/refresh")
async def refresh_materials(
    request: Request,
    material_id: str,
    user = Depends(protect)
):
    return await refresh_study_materials(request, material_id, user)

@router.delete("/{material_id}")
async def delete_materials(
    request: Request,
    material_id: str,
    user = Depends(protect)
):
    return await delete_study_materials(request, material_id, user)
