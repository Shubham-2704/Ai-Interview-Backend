from pydantic import BaseModel
from typing import Optional, List
from models.question_model import Question


class SessionCreate(BaseModel):
    role : str
    experience : int
    topicsToFocus : str
    description : str
    questions: Optional[List[Question]] = None