from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

class StudyMaterialLink(BaseModel):
    title: str
    url: str
    source: Optional[str] = None
    duration: Optional[str] = None
    platform: Optional[str] = None
    difficulty: Optional[str] = None
    rating: Optional[float] = None

class StudyMaterialBase(BaseModel):
    session_id: str
    question_id: str
    question_text: str
    role: str
    experience_level: str
    
    # Material categories
    youtube_links: List[StudyMaterialLink] = Field(default_factory=list)
    articles: List[StudyMaterialLink] = Field(default_factory=list)
    documentation: List[StudyMaterialLink] = Field(default_factory=list)
    practice_links: List[StudyMaterialLink] = Field(default_factory=list)
    books: List[StudyMaterialLink] = Field(default_factory=list)
    courses: List[StudyMaterialLink] = Field(default_factory=list)
    
    # Metadata
    ai_model_used: Optional[str] = None
    search_query: str
    keywords: List[str] = Field(default_factory=list)
    total_sources: int = Field(default=0)

class StudyMaterialCreate(StudyMaterialBase):
    pass

class StudyMaterialInDB(StudyMaterialBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class StudyMaterialResponse(StudyMaterialBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

class StudyMaterialRequest(BaseModel):
    question: str
    force_refresh: Optional[bool] = False

class TavilySearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=5, ge=1, le=10)
    search_depth: str = Field(default="advanced", pattern="^(basic|advanced)$")
