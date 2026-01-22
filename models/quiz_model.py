from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class GenerateQuizRequest(BaseModel):
    sessionId: str
    numberOfQuestions: int = Field(..., ge=1, le=50)

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correctAnswer: int = Field(..., ge=0, le=3)
    explanation: str

class QuizSubmission(BaseModel):
    quizId: str
    answers: List[int] = Field(..., min_items=1)  # List of selected option indexes
    timeSpent: Optional[int] = 0  # in seconds

class QuizResult(BaseModel):
    score: int
    total: int
    percentage: float
    questions: List[Dict[str, Any]]
    feedback: str
    timeSpent: int
    completedAt: datetime
