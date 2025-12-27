from pydantic import BaseModel
from typing import Optional, List
from typing import Optional

class Question(BaseModel):
    question: str
    answer: str 
    topic: Optional[str] = None
    isPinned: bool = False

class AddQuestionsRequest(BaseModel):
    sessionId: str
    questions: List[Question]

class UpdateNoteRequest(BaseModel):
    note: Optional[str] = ""

# New model for API response with explanation
class QuestionWithExplanation(Question):
    explanationTitle: Optional[str] = None
    explanation: Optional[str] = None