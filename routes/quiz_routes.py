from fastapi import APIRouter, Depends, Query
from middlewares.auth_middlewares import protect
from controllers.quiz_controller import *
from models.quiz_model import *

router = APIRouter(prefix="/api/quiz", tags=["Quiz"])

@router.post("/generate")
async def generate_quiz(
    data: GenerateQuizRequest,
    user = Depends(protect)
):
    return await generate_quiz_service(
        data.sessionId,
        data.numberOfQuestions,
        user
    )

@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: str,
    data: QuizSubmission,
    user = Depends(protect)
):
    return await submit_quiz_service(
        quiz_id,
        data.answers,
        data.timeSpent,
        user
    )

@router.get("/{quiz_id}/results")
async def get_quiz_results(
    quiz_id: str,
    user = Depends(protect)
):
    return await get_quiz_results_service(quiz_id, user)

@router.get("/session/{session_id}")
async def get_session_quizzes(
    session_id: str,
    user = Depends(protect)
):
    return await get_user_quizzes_service(session_id, user)

@router.delete("/{quiz_id}")
async def delete_quiz(
    quiz_id: str,
    user = Depends(protect)
):
    return await delete_quiz_service(quiz_id, user)

@router.get("/session/{session_id}/analytics")
async def get_quiz_analytics(
    session_id: str,
    range: str = Query("all", description="Time range: week, month, all"),
    user = Depends(protect)
):
    return await get_quiz_analytics_service(session_id, range, user)

@router.get("/session/{session_id}/topics")
async def get_topic_performance(
    session_id: str,
    user = Depends(protect)
):
    return await get_topic_performance_service(session_id, user)

@router.post("/{quiz_id}/track-time")
async def track_question_time(
    quiz_id: str,
    data: TrackTimeRequest,
    user = Depends(protect)
):
    return await track_question_time_service(quiz_id, data.questionIndex, user)